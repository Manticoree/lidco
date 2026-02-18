"""SQLite database layer for the project index.

IndexDatabase is a thin, focused wrapper around sqlite3.  It handles only
persistence: opening/creating the database, applying the schema, and
providing CRUD methods.  All business logic lives in ProjectIndexer.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from lidco.index.schema import (
    SCHEMA_SQL,
    FileRecord,
    ImportRecord,
    IndexStats,
    SymbolRecord,
)


class IndexDatabase:
    """SQLite-backed store for project index data."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._apply_schema()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _apply_schema(self) -> None:
        """Apply DDL statements (idempotent — uses CREATE IF NOT EXISTS)."""
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    # ── Files ─────────────────────────────────────────────────────────────────

    def upsert_file(self, record: FileRecord) -> int:
        """Insert or replace a file record. Returns the row id."""
        self._conn.execute(
            """
            INSERT INTO files (path, language, role, size_bytes, mtime, lines_count, indexed_at)
            VALUES (:path, :language, :role, :size_bytes, :mtime, :lines_count, :indexed_at)
            ON CONFLICT(path) DO UPDATE SET
                language    = excluded.language,
                role        = excluded.role,
                size_bytes  = excluded.size_bytes,
                mtime       = excluded.mtime,
                lines_count = excluded.lines_count,
                indexed_at  = excluded.indexed_at
            """,
            {
                "path": record.path,
                "language": record.language,
                "role": record.role,
                "size_bytes": record.size_bytes,
                "mtime": record.mtime,
                "lines_count": record.lines_count,
                "indexed_at": record.indexed_at,
            },
        )
        self._conn.commit()
        # Always look up the actual row id — lastrowid is unreliable for
        # ON CONFLICT DO UPDATE on some platforms (returns AUTOINCREMENT
        # counter rather than the existing row's rowid).
        return self._get_file_id(record.path)

    def get_file_by_path(self, path: str) -> FileRecord | None:
        """Return a FileRecord for the given relative path, or None."""
        row = self._conn.execute(
            "SELECT * FROM files WHERE path = ?", (path,)
        ).fetchone()
        return _row_to_file(row) if row else None

    def get_file_id(self, path: str) -> int | None:
        """Return the row id for a path, or None if not found."""
        row = self._conn.execute(
            "SELECT id FROM files WHERE path = ?", (path,)
        ).fetchone()
        return row["id"] if row else None

    def delete_file(self, path: str) -> None:
        """Remove a file and all its symbols/imports (CASCADE)."""
        self._conn.execute("DELETE FROM files WHERE path = ?", (path,))
        self._conn.commit()

    def list_file_mtimes(self) -> dict[str, float]:
        """Return {relative_path: mtime} for all indexed files."""
        rows = self._conn.execute("SELECT path, mtime FROM files").fetchall()
        return {row["path"]: row["mtime"] for row in rows}

    def query_files_by_role(self, role: str) -> list[FileRecord]:
        """Return all files with the given role."""
        rows = self._conn.execute(
            "SELECT * FROM files WHERE role = ?", (role,)
        ).fetchall()
        return [_row_to_file(r) for r in rows]

    def list_all_files(self) -> list[FileRecord]:
        """Return every indexed file ordered by path."""
        rows = self._conn.execute("SELECT * FROM files ORDER BY path").fetchall()
        return [_row_to_file(r) for r in rows]

    def get_file_by_id(self, file_id: int) -> FileRecord | None:
        """Return a FileRecord by its integer id, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        return _row_to_file(row) if row else None

    # ── Symbols ───────────────────────────────────────────────────────────────

    def insert_symbols(self, records: list[SymbolRecord]) -> None:
        """Bulk-insert symbols for a file (existing ones deleted first via CASCADE)."""
        if not records:
            return
        self._conn.executemany(
            """
            INSERT INTO symbols (file_id, name, kind, line_start, line_end, is_exported, parent_name)
            VALUES (:file_id, :name, :kind, :line_start, :line_end, :is_exported, :parent_name)
            """,
            [
                {
                    "file_id": r.file_id,
                    "name": r.name,
                    "kind": r.kind,
                    "line_start": r.line_start,
                    "line_end": r.line_end,
                    "is_exported": int(r.is_exported),
                    "parent_name": r.parent_name,
                }
                for r in records
            ],
        )
        self._conn.commit()

    def delete_symbols_for_file(self, file_id: int) -> None:
        """Remove all symbols for a file (used before re-indexing)."""
        self._conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
        self._conn.commit()

    def query_symbols(
        self,
        name_like: str | None = None,
        kind: str | None = None,
        file_id: int | None = None,
    ) -> list[SymbolRecord]:
        """Query symbols with optional filters."""
        clauses: list[str] = []
        params: list[Any] = []

        if name_like is not None:
            clauses.append("name LIKE ?")
            params.append(name_like)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if file_id is not None:
            clauses.append("file_id = ?")
            params.append(file_id)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM symbols {where} ORDER BY line_start", params
        ).fetchall()
        return [_row_to_symbol(r) for r in rows]

    # ── Imports ───────────────────────────────────────────────────────────────

    def insert_imports(self, records: list[ImportRecord]) -> None:
        """Bulk-insert import records for a file."""
        if not records:
            return
        self._conn.executemany(
            """
            INSERT INTO imports (from_file_id, imported_module, resolved_path, import_kind)
            VALUES (:from_file_id, :imported_module, :resolved_path, :import_kind)
            """,
            [
                {
                    "from_file_id": r.from_file_id,
                    "imported_module": r.imported_module,
                    "resolved_path": r.resolved_path,
                    "import_kind": r.import_kind,
                }
                for r in records
            ],
        )
        self._conn.commit()

    def delete_imports_for_file(self, file_id: int) -> None:
        """Remove all imports for a file (used before re-indexing)."""
        self._conn.execute("DELETE FROM imports WHERE from_file_id = ?", (file_id,))
        self._conn.commit()

    def query_imports_for_file(self, file_id: int) -> list[ImportRecord]:
        """Return all import records for a given file."""
        rows = self._conn.execute(
            "SELECT * FROM imports WHERE from_file_id = ?", (file_id,)
        ).fetchall()
        return [_row_to_import(r) for r in rows]

    def query_files_importing(self, path_fragment: str) -> list[str]:
        """Return paths of files that import a module matching path_fragment."""
        rows = self._conn.execute(
            """
            SELECT DISTINCT f.path
            FROM files f
            JOIN imports i ON i.from_file_id = f.id
            WHERE i.resolved_path LIKE ?
            ORDER BY f.path
            """,
            (f"%{path_fragment}%",),
        ).fetchall()
        return [r["path"] for r in rows]

    # ── Meta ──────────────────────────────────────────────────────────────────

    def set_meta(self, key: str, value: str) -> None:
        """Upsert a metadata key-value pair."""
        self._conn.execute(
            "INSERT INTO index_meta (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    def get_meta(self, key: str) -> str | None:
        """Return a metadata value by key, or None."""
        row = self._conn.execute(
            "SELECT value FROM index_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> IndexStats:
        """Return aggregate statistics about the current index."""
        total_files = self._conn.execute(
            "SELECT COUNT(*) FROM files"
        ).fetchone()[0]

        total_symbols = self._conn.execute(
            "SELECT COUNT(*) FROM symbols"
        ).fetchone()[0]

        total_imports = self._conn.execute(
            "SELECT COUNT(*) FROM imports"
        ).fetchone()[0]

        last_indexed_str = self.get_meta("last_indexed_at")
        last_indexed_at = float(last_indexed_str) if last_indexed_str else None

        role_rows = self._conn.execute(
            "SELECT role, COUNT(*) as cnt FROM files GROUP BY role"
        ).fetchall()
        files_by_role = {r["role"]: r["cnt"] for r in role_rows}

        lang_rows = self._conn.execute(
            "SELECT language, COUNT(*) as cnt FROM files GROUP BY language"
        ).fetchall()
        files_by_language = {r["language"]: r["cnt"] for r in lang_rows}

        return IndexStats(
            total_files=total_files,
            total_symbols=total_symbols,
            total_imports=total_imports,
            last_indexed_at=last_indexed_at,
            files_by_role=files_by_role,
            files_by_language=files_by_language,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> IndexDatabase:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_file_id(self, path: str) -> int:
        row = self._conn.execute(
            "SELECT id FROM files WHERE path = ?", (path,)
        ).fetchone()
        return row["id"] if row else 0


# ── Row mappers ───────────────────────────────────────────────────────────────

def _row_to_file(row: sqlite3.Row) -> FileRecord:
    return FileRecord(
        id=row["id"],
        path=row["path"],
        language=row["language"],
        role=row["role"],
        size_bytes=row["size_bytes"],
        mtime=row["mtime"],
        lines_count=row["lines_count"],
        indexed_at=row["indexed_at"],
    )


def _row_to_symbol(row: sqlite3.Row) -> SymbolRecord:
    return SymbolRecord(
        id=row["id"],
        file_id=row["file_id"],
        name=row["name"],
        kind=row["kind"],
        line_start=row["line_start"],
        line_end=row["line_end"],
        is_exported=bool(row["is_exported"]),
        parent_name=row["parent_name"],
    )


def _row_to_import(row: sqlite3.Row) -> ImportRecord:
    return ImportRecord(
        id=row["id"],
        from_file_id=row["from_file_id"],
        imported_module=row["imported_module"],
        resolved_path=row["resolved_path"],
        import_kind=row["import_kind"],
    )
