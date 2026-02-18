"""CodemapGenerator — render a CODEMAPS.md document from the project index.

Reads files, symbols and stats from IndexDatabase and produces a structured
Markdown file that gives an AI (or human) a bird's-eye view of the codebase:

  • Stats header (file / symbol / import counts, timestamp)
  • Sections for each file role (entrypoint → config → model → … → test)
  • Per-file symbol listing with classes, methods, functions and constants
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

from lidco.index.db import IndexDatabase
from lidco.index.schema import FileRecord, SymbolRecord

logger = logging.getLogger(__name__)

# ── Display configuration ─────────────────────────────────────────────────────

# Sections appear in this order; roles not in this list are appended at the end.
_ROLE_ORDER: list[str] = [
    "entrypoint",
    "config",
    "model",
    "router",
    "utility",
    "test",
    "unknown",
]

_ROLE_HEADINGS: dict[str, str] = {
    "entrypoint": "Entrypoints",
    "config":     "Config",
    "model":      "Models",
    "router":     "Routers",
    "utility":    "Utilities",
    "test":       "Tests",
    "unknown":    "Other",
}


class CodemapGenerator:
    """Generate a CODEMAPS.md document from an ``IndexDatabase``.

    Parameters
    ----------
    db:
        Open ``IndexDatabase`` instance (caller owns lifecycle).
    """

    def __init__(self, db: IndexDatabase) -> None:
        self._db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(self) -> str:
        """Return the full CODEMAPS.md content as a string."""
        stats = self._db.get_stats()
        parts: list[str] = []

        # ── Header ────────────────────────────────────────────────────────────
        parts.append("# Project Codemap\n")

        ts_prefix = ""
        if stats.last_indexed_at is not None:
            dt = datetime.datetime.fromtimestamp(
                stats.last_indexed_at, tz=datetime.timezone.utc
            )
            ts_prefix = f"Indexed: {dt.strftime('%Y-%m-%d %H:%M')} UTC · "

        parts.append(
            f"> {ts_prefix}"
            f"{stats.total_files} files · "
            f"{stats.total_symbols} symbols · "
            f"{stats.total_imports} imports\n"
        )

        # Language breakdown — only shown when there are multiple languages
        if len(stats.files_by_language) > 1:
            lang_summary = ", ".join(
                f"{cnt} {lang}"
                for lang, cnt in sorted(stats.files_by_language.items())
            )
            parts.append(f"> Languages: {lang_summary}\n")

        # ── Sections by role ──────────────────────────────────────────────────
        # Collect all roles that have files, preserving defined display order.
        roles_with_files = {
            role for role in _ROLE_ORDER
            if self._db.query_files_by_role(role)
        }
        ordered = [r for r in _ROLE_ORDER if r in roles_with_files]

        for role in ordered:
            files = self._db.query_files_by_role(role)
            heading = _ROLE_HEADINGS.get(role, role.title())
            parts.append(f"\n## {heading}\n")

            for file in sorted(files, key=lambda f: f.path):
                symbols = self._db.query_symbols(file_id=file.id)
                parts.append(self._render_file(file, symbols))

        return "\n".join(parts)

    def write(self, output_path: Path) -> None:
        """Write the codemap to *output_path*, creating parent dirs if needed."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate()
        output_path.write_text(content, encoding="utf-8")
        logger.info("Wrote codemap (%d chars) to %s", len(content), output_path)

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _render_file(file: FileRecord, symbols: list[SymbolRecord]) -> str:
        """Render one file as a Markdown subsection."""
        meta = f"{file.language}, {file.lines_count} lines"
        heading = f"### `{file.path}` ({meta})"

        if not symbols:
            return f"{heading}\n*(no symbols)*\n"

        lines: list[str] = [heading]

        # Separate into classes (with their methods) and other top-level symbols.
        classes   = [s for s in symbols if s.kind == "class"]
        methods   = {s for s in symbols if s.kind == "method"}
        top_level = [s for s in symbols if s.kind not in ("class", "method")]

        for cls in sorted(classes, key=lambda s: s.line_start):
            priv = " *(private)*" if not cls.is_exported else ""
            lines.append(f"- `{cls.name}` class{priv}")
            for m in sorted(
                (s for s in methods if s.parent_name == cls.name),
                key=lambda s: s.line_start,
            ):
                m_priv = " *(private)*" if not m.is_exported else ""
                lines.append(f"  - `{m.name}` method{m_priv}")

        for sym in sorted(top_level, key=lambda s: s.line_start):
            priv = " *(private)*" if not sym.is_exported else ""
            lines.append(f"- `{sym.name}` {sym.kind}{priv}")

        return "\n".join(lines) + "\n"
