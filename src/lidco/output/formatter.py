"""Output formatter — task 1075.

Utility for formatting markdown, JSON, tables, and diffs for terminal display.
"""
from __future__ import annotations

import json
from typing import Any, Sequence


class OutputFormatter:
    """Formats structured data for terminal output."""

    def __init__(self, width: int = 80, use_color: bool = True) -> None:
        self._width = width
        self._use_color = use_color

    @property
    def width(self) -> int:
        return self._width

    @property
    def use_color(self) -> bool:
        return self._use_color

    def format_markdown(self, text: str) -> str:
        """Convert basic markdown to plain-text with emphasis markers.

        Handles headings (``#``), bold (``**``), inline code, and code blocks.
        """
        lines: list[str] = []
        in_code_block = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                lines.append("---" if not in_code_block else "")
                continue
            if in_code_block:
                lines.append(f"  | {line}")
                continue
            if stripped.startswith("# "):
                heading = stripped[2:].strip().upper()
                lines.append(heading)
                lines.append("=" * min(len(heading), self._width))
            elif stripped.startswith("## "):
                heading = stripped[3:].strip()
                lines.append(heading)
                lines.append("-" * min(len(heading), self._width))
            elif stripped.startswith("### "):
                lines.append(stripped[4:].strip())
            else:
                # Bold markers
                processed = stripped.replace("**", "*")
                lines.append(processed)
        return "\n".join(lines)

    def format_json(self, data: Any) -> str:
        """Pretty-print *data* as indented JSON."""
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    def format_table(self, rows: Sequence[Sequence[str]], columns: Sequence[str]) -> str:
        """Render *rows* as a text table with *columns* as headers.

        Each column is sized to the widest entry (header or cell).
        """
        if not columns:
            return ""

        col_widths = [len(c) for c in columns]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        def _fmt_row(cells: Sequence[str]) -> str:
            parts = []
            for i, cell in enumerate(cells):
                w = col_widths[i] if i < len(col_widths) else len(str(cell))
                parts.append(str(cell).ljust(w))
            return " | ".join(parts)

        header = _fmt_row(columns)
        sep = "-+-".join("-" * w for w in col_widths)
        body_lines = [_fmt_row(r) for r in rows]
        return "\n".join([header, sep, *body_lines])

    def format_diff(self, old: str, new: str) -> str:
        """Generate a unified-style diff between *old* and *new* text."""
        old_lines = old.splitlines()
        new_lines = new.splitlines()
        result: list[str] = []
        result.append("--- old")
        result.append("+++ new")

        max_len = max(len(old_lines), len(new_lines))
        for i in range(max_len):
            old_line = old_lines[i] if i < len(old_lines) else None
            new_line = new_lines[i] if i < len(new_lines) else None
            if old_line == new_line:
                result.append(f" {old_line}")
            else:
                if old_line is not None:
                    result.append(f"-{old_line}")
                if new_line is not None:
                    result.append(f"+{new_line}")
        return "\n".join(result)

    def truncate(self, text: str, max_lines: int) -> str:
        """Truncate *text* to *max_lines*, appending an indicator if cut."""
        lines = text.splitlines()
        if len(lines) <= max_lines:
            return text
        kept = lines[:max_lines]
        kept.append(f"... ({len(lines) - max_lines} more lines)")
        return "\n".join(kept)
