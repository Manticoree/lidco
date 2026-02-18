"""ProjectIndexer — full and incremental indexing of a project directory.

Orchestrates AstAnalyzer + IndexDatabase to build and maintain a
structural index of the user's project.  Two entry points:

  run_full_index()        — scan every supported file, replace all data
  run_incremental_index() — only (re)index files whose mtime changed,
                            delete records for files that no longer exist

Staleness helpers let callers decide whether re-indexing is warranted:

  is_stale(hours)    — True if last index is older than *hours*
  has_new_files()    — True if any file on disk has mtime > last recorded mtime
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from lidco.index.ast_analyzer import AstAnalyzer
from lidco.index.db import IndexDatabase
from lidco.index.schema import FileRecord, ImportRecord, IndexStats, SymbolRecord
from lidco.rag.indexer import EXTENSION_TO_LANGUAGE, SKIP_DIRS, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)

_META_LAST_INDEXED = "last_indexed_at"
_META_MAX_MTIME = "max_file_mtime"


@dataclass(frozen=True)
class IndexResult:
    """Summary returned after an indexing run."""

    added: int
    updated: int
    deleted: int
    skipped: int
    stats: IndexStats


class ProjectIndexer:
    """Index a project directory into SQLite for fast structural queries.

    Parameters
    ----------
    project_dir:
        Root of the project to index.
    db:
        Open ``IndexDatabase`` instance (caller owns lifecycle).
    max_file_size_kb:
        Files larger than this are skipped (avoids giant auto-generated files).
    """

    def __init__(
        self,
        project_dir: Path,
        db: IndexDatabase,
        max_file_size_kb: int = 500,
    ) -> None:
        self._project_dir = project_dir.resolve()
        self._db = db
        self._max_bytes = max_file_size_kb * 1024
        self._analyzer = AstAnalyzer()

    # ── Public: indexing ──────────────────────────────────────────────────────

    def run_full_index(
        self,
        progress_callback: object = None,
    ) -> IndexResult:
        """Scan every supported file and rebuild the index from scratch.

        Existing data is replaced — stale records for deleted files are
        automatically removed as part of the reconciliation step.
        """
        files = self._collect_files()
        added = updated = skipped = 0

        for i, abs_path in enumerate(files):
            if progress_callback is not None:
                try:
                    progress_callback(i + 1, len(files), abs_path.name)
                except Exception as exc:
                    logger.debug("Progress callback error (full index): %s", exc)

            rel = abs_path.relative_to(self._project_dir).as_posix()
            outcome = self._index_one(abs_path, rel)
            if outcome == "added":
                added += 1
            elif outcome == "updated":
                updated += 1
            else:
                skipped += 1

        # Remove records for files no longer on disk
        deleted = self._delete_missing(files)

        now = time.time()
        self._db.set_meta(_META_LAST_INDEXED, str(now))
        self._db.set_meta(_META_MAX_MTIME, str(self._max_mtime(files)))

        stats = self._db.get_stats()
        logger.info(
            "Full index: +%d updated=%d deleted=%d skipped=%d | %d files %d symbols",
            added, updated, deleted, skipped, stats.total_files, stats.total_symbols,
        )
        return IndexResult(
            added=added, updated=updated, deleted=deleted,
            skipped=skipped, stats=stats,
        )

    def run_incremental_index(
        self,
        progress_callback: object = None,
    ) -> IndexResult:
        """Re-index only files that changed since the last run.

        New files are added, modified files are re-indexed, and records for
        deleted files are removed.  Unchanged files are not touched.
        """
        stored_mtimes = self._db.list_file_mtimes()
        files_on_disk = self._collect_files()
        disk_map: dict[str, Path] = {
            f.relative_to(self._project_dir).as_posix(): f for f in files_on_disk
        }

        added = updated = deleted = skipped = 0
        work: list[tuple[Path, str, bool]] = []  # (abs_path, rel, is_new)

        for rel, abs_path in disk_map.items():
            try:
                mtime = abs_path.stat().st_mtime
            except OSError:
                continue
            stored = stored_mtimes.get(rel)
            if stored is None:
                work.append((abs_path, rel, True))
            elif mtime != stored:
                work.append((abs_path, rel, False))
            else:
                skipped += 1

        for i, (abs_path, rel, is_new) in enumerate(work):
            if progress_callback is not None:
                try:
                    progress_callback(i + 1, len(work), abs_path.name)
                except Exception as exc:
                    logger.debug("Progress callback error (incremental index): %s", exc)
            outcome = self._index_one(abs_path, rel)
            if outcome == "skipped":
                skipped += 1
            elif is_new:
                added += 1
            else:
                updated += 1

        # Remove records for files deleted from disk
        for rel in list(stored_mtimes):
            if rel not in disk_map:
                self._db.delete_file(rel)
                deleted += 1

        now = time.time()
        self._db.set_meta(_META_LAST_INDEXED, str(now))
        if files_on_disk:
            self._db.set_meta(_META_MAX_MTIME, str(self._max_mtime(files_on_disk)))

        stats = self._db.get_stats()
        logger.info(
            "Incremental index: +%d updated=%d deleted=%d skipped=%d",
            added, updated, deleted, skipped,
        )
        return IndexResult(
            added=added, updated=updated, deleted=deleted,
            skipped=skipped, stats=stats,
        )

    # ── Public: staleness helpers ─────────────────────────────────────────────

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Return True if the index has never been built or is older than *max_age_hours*."""
        val = self._db.get_meta(_META_LAST_INDEXED)
        if val is None:
            return True
        try:
            last = float(val)
        except ValueError:
            return True
        return (time.time() - last) > max_age_hours * 3600

    def has_new_files(self) -> bool:
        """Return True if any file on disk is newer than the last recorded max mtime."""
        val = self._db.get_meta(_META_MAX_MTIME)
        if val is None:
            return True
        try:
            stored_max = float(val)
        except ValueError:
            return True

        for abs_path in self._collect_files():
            try:
                if abs_path.stat().st_mtime > stored_max:
                    return True
            except OSError:
                continue
        return False

    def get_stats(self) -> IndexStats:
        """Delegate to the underlying database."""
        return self._db.get_stats()

    @property
    def db(self) -> IndexDatabase:
        """Direct access to the underlying database (for queries)."""
        return self._db

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _collect_files(self) -> list[Path]:
        """Return all indexable files under project_dir, sorted for reproducibility."""
        result: list[Path] = []
        try:
            for path in sorted(self._project_dir.rglob("*")):
                if any(part in SKIP_DIRS for part in path.parts):
                    continue
                if not path.is_file():
                    continue
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                try:
                    if path.stat().st_size > self._max_bytes:
                        logger.debug("Skipping large file: %s", path)
                        continue
                except OSError:
                    continue
                result.append(path)
        except OSError as exc:
            logger.warning("Error scanning project dir: %s", exc)
        return result

    def _index_one(self, abs_path: Path, rel: str) -> str:
        """Index a single file.  Returns 'added', 'updated', or 'skipped'."""
        try:
            stat = abs_path.stat()
        except OSError as exc:
            logger.debug("Cannot stat %s: %s", abs_path, exc)
            return "skipped"

        language = EXTENSION_TO_LANGUAGE.get(abs_path.suffix.lower(), "unknown")

        # Read line count cheaply
        try:
            lines_count = sum(1 for _ in abs_path.open(encoding="utf-8", errors="replace"))
        except OSError:
            lines_count = 0

        is_new = self._db.get_file_id(rel) is None

        record = FileRecord(
            path=rel,
            language=language,
            role="unknown",  # filled in after symbol analysis
            size_bytes=stat.st_size,
            mtime=stat.st_mtime,
            lines_count=lines_count,
            indexed_at=time.time(),
        )

        # Analyse symbols and imports first (need them for role detection)
        symbols_raw, imports_raw = self._analyzer.analyze(abs_path)
        role = self._analyzer.detect_file_role(abs_path, symbols_raw)

        # Persist file with correct role
        record = FileRecord(
            path=rel,
            language=language,
            role=role,
            size_bytes=stat.st_size,
            mtime=stat.st_mtime,
            lines_count=lines_count,
            indexed_at=time.time(),
        )
        file_id = self._db.upsert_file(record)

        # Replace symbols and imports (delete old first, then insert fresh)
        self._db.delete_symbols_for_file(file_id)
        self._db.delete_imports_for_file(file_id)

        symbols = [
            SymbolRecord(
                file_id=file_id,
                name=s.name,
                kind=s.kind,
                line_start=s.line_start,
                line_end=s.line_end,
                is_exported=s.is_exported,
                parent_name=s.parent_name,
            )
            for s in symbols_raw
        ]
        imports = [
            ImportRecord(
                from_file_id=file_id,
                imported_module=i.imported_module,
                resolved_path=i.resolved_path,
                import_kind=i.import_kind,
            )
            for i in imports_raw
        ]

        self._db.insert_symbols(symbols)
        self._db.insert_imports(imports)

        return "added" if is_new else "updated"

    @staticmethod
    def _max_mtime(files: list[Path]) -> float:
        """Return the maximum mtime across *files*, or 0.0 if empty."""
        result = 0.0
        for f in files:
            try:
                result = max(result, f.stat().st_mtime)
            except OSError:
                continue
        return result

    def _delete_missing(self, current_files: list[Path]) -> int:
        """Remove index entries for files no longer present on disk."""
        on_disk = {
            f.relative_to(self._project_dir).as_posix() for f in current_files
        }
        stored = set(self._db.list_file_mtimes())
        deleted = 0
        for rel in stored - on_disk:
            self._db.delete_file(rel)
            deleted += 1
        return deleted
