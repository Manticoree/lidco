"""IndexContextEnricher — compact structural context for agent system prompts.

Unlike CodemapGenerator (which produces a full human-readable CODEMAPS.md),
this class emits short, token-efficient strings tailored for AI consumption:

  • get_project_summary()   — one-liner stats (files, languages, roles)
  • get_context(query)      — summary + entrypoints + query-relevant files

When the index is empty the methods return empty strings so callers can
safely include the output without guarding against None.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path

from lidco.index.db import IndexDatabase
from lidco.index.schema import FileRecord

logger = logging.getLogger(__name__)


class IndexContextEnricher:
    """Read from ``IndexDatabase`` and produce compact context strings.

    Parameters
    ----------
    db:
        Open ``IndexDatabase`` instance (caller owns lifecycle).
    """

    def __init__(self, db: IndexDatabase) -> None:
        self._db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def is_indexed(self) -> bool:
        """Return True if the index contains at least one file."""
        return self._db.get_stats().total_files > 0

    def get_project_summary(self) -> str:
        """Return a one-line structural summary suitable for a system prompt.

        Returns an empty string if the index is empty.
        """
        stats = self._db.get_stats()
        if stats.total_files == 0:
            return ""

        parts: list[str] = [
            f"{stats.total_files} files",
            f"{stats.total_symbols} symbols",
        ]

        if stats.files_by_language:
            lang_parts = ", ".join(
                f"{cnt} {lang}"
                for lang, cnt in sorted(
                    stats.files_by_language.items(), key=lambda kv: -kv[1]
                )
            )
            parts.append(f"languages: {lang_parts}")

        return "Project index: " + " · ".join(parts) + "."

    def get_entrypoints(self) -> list[FileRecord]:
        """Return all files with role 'entrypoint'."""
        return self._db.query_files_by_role("entrypoint")

    def find_relevant_files(
        self,
        query: str,
        limit: int = 5,
    ) -> list[FileRecord]:
        """Return files most relevant to *query* using keyword matching.

        Scoring:
        • +2 per query term that appears in a symbol name
        • +1 per query term that appears in a file path

        Files with score 0 are excluded.
        """
        if not query.strip():
            return []

        terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        if not terms:
            return []

        scores: dict[int, int] = defaultdict(int)

        # Symbol-name matches (higher weight)
        for term in terms:
            for sym in self._db.query_symbols(name_like=f"%{term}%"):
                scores[sym.file_id] += 2

        # Path substring matches
        for file in self._db.list_all_files():
            path_lower = file.path.lower()
            for term in terms:
                if term in path_lower:
                    scores[file.id] += 1

        top_ids = sorted(scores, key=lambda fid: -scores[fid])[:limit]
        result: list[FileRecord] = []
        for fid in top_ids:
            rec = self._db.get_file_by_id(fid)
            if rec is not None:
                result.append(rec)
        return result

    def get_context(self, query: str = "", max_chars: int = 3000) -> str:
        """Return a compact structural context string for agent injection.

        Includes:
        1. Project summary line
        2. Entrypoints (if any)
        3. Query-relevant files with their top symbols (when *query* provided)

        Returns an empty string if the index is empty.
        Truncates at *max_chars* to stay token-budget-friendly.
        """
        if not self.is_indexed():
            return ""

        lines: list[str] = []

        summary = self.get_project_summary()
        if summary:
            lines.append(summary)

        # Entrypoints
        entrypoints = self.get_entrypoints()
        if entrypoints:
            ep_paths = ", ".join(f"`{f.path}`" for f in entrypoints[:5])
            if len(entrypoints) > 5:
                ep_paths += f" (+{len(entrypoints) - 5} more)"
            lines.append(f"Entrypoints: {ep_paths}.")

        # Query-relevant files
        if query:
            relevant = self.find_relevant_files(query)
            if relevant:
                lines.append("Relevant files for this query:")
                for f in relevant:
                    symbols = self._db.query_symbols(file_id=f.id)
                    # Only top-level (non-method) symbols for brevity
                    top_syms = [s for s in symbols if s.kind != "method"][:4]
                    sym_str = ", ".join(f"`{s.name}`" for s in top_syms)
                    suffix = f" — {sym_str}" if sym_str else ""
                    lines.append(f"  - `{f.path}` ({f.language}){suffix}")

        result = "\n".join(lines)
        if len(result) > max_chars:
            result = result[: max_chars - 3] + "..."
        return result

    # ── Class-level factory ───────────────────────────────────────────────────

    @classmethod
    def from_project_dir(cls, project_dir: Path) -> IndexContextEnricher | None:
        """Open the index DB for *project_dir* and return an enricher.

        Returns None if the database file does not exist yet (index not built).
        """
        db_path = project_dir / ".lidco" / "project_index.db"
        if not db_path.exists():
            return None
        try:
            db = IndexDatabase(db_path)
            return cls(db)
        except Exception as exc:
            logger.debug("Could not open project index at %s: %s", db_path, exc)
            return None
