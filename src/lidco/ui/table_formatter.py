"""ASCII / Markdown table formatter (Q139/828)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Union

_SENTINEL = object()


@dataclass
class Column:
    """Column definition for a table."""

    name: str
    width: Optional[int] = None
    align: str = "left"
    min_width: int = 3


class _SeparatorRow:
    """Marker for a horizontal separator."""


class TableFormatter:
    """Formats tabular data as ASCII, compact, or Markdown tables."""

    def __init__(self, columns: list[Union[str, Column]]) -> None:
        self._columns: list[Column] = []
        for c in columns:
            if isinstance(c, str):
                self._columns.append(Column(name=c))
            else:
                self._columns.append(c)
        self._rows: list[list[str] | _SeparatorRow] = []

    # -- mutators ----------------------------------------------------------

    def add_row(self, *values: object) -> None:
        """Append a data row.  Values are stringified."""
        row = [str(v) for v in values]
        # Pad or truncate to column count
        while len(row) < len(self._columns):
            row.append("")
        self._rows.append(row[: len(self._columns)])

    def add_separator(self) -> None:
        """Insert a horizontal separator line."""
        self._rows.append(_SeparatorRow())

    def clear(self) -> None:
        """Remove all rows."""
        self._rows.clear()

    # -- queries -----------------------------------------------------------

    @property
    def row_count(self) -> int:
        """Number of data rows (excludes separators)."""
        return sum(1 for r in self._rows if not isinstance(r, _SeparatorRow))

    # -- width calculation -------------------------------------------------

    def _effective_widths(self) -> list[int]:
        """Compute column widths from content (header + data)."""
        widths: list[int] = []
        for i, col in enumerate(self._columns):
            if col.width is not None:
                widths.append(max(col.width, col.min_width))
            else:
                max_w = len(col.name)
                for row in self._rows:
                    if isinstance(row, _SeparatorRow):
                        continue
                    if i < len(row):
                        max_w = max(max_w, len(row[i]))
                widths.append(max(max_w, col.min_width))
        return widths

    def _align_cell(self, text: str, width: int, align: str) -> str:
        if align == "right":
            return text.rjust(width)
        if align == "center":
            return text.center(width)
        return text.ljust(width)

    # -- renderers ---------------------------------------------------------

    def render(self) -> str:
        """Render a bordered ASCII table."""
        widths = self._effective_widths()
        lines: list[str] = []

        def hline() -> str:
            return "+" + "+".join("-" * (w + 2) for w in widths) + "+"

        def data_line(cells: list[str]) -> str:
            parts: list[str] = []
            for i, col in enumerate(self._columns):
                val = cells[i] if i < len(cells) else ""
                parts.append(" " + self._align_cell(val, widths[i], col.align) + " ")
            return "|" + "|".join(parts) + "|"

        # Header
        lines.append(hline())
        lines.append(data_line([c.name for c in self._columns]))
        lines.append(hline())

        # Rows
        for row in self._rows:
            if isinstance(row, _SeparatorRow):
                lines.append(hline())
            else:
                lines.append(data_line(row))

        lines.append(hline())
        return "\n".join(lines)

    def render_compact(self) -> str:
        """Render a compact table (no borders, space-separated)."""
        widths = self._effective_widths()
        lines: list[str] = []

        def fmt(cells: list[str]) -> str:
            parts: list[str] = []
            for i, col in enumerate(self._columns):
                val = cells[i] if i < len(cells) else ""
                parts.append(self._align_cell(val, widths[i], col.align))
            return "  ".join(parts)

        lines.append(fmt([c.name for c in self._columns]))
        for row in self._rows:
            if isinstance(row, _SeparatorRow):
                continue  # skip separators in compact mode
            lines.append(fmt(row))
        return "\n".join(lines)

    def render_markdown(self) -> str:
        """Render a Markdown-formatted table."""
        widths = self._effective_widths()
        lines: list[str] = []

        def md_row(cells: list[str]) -> str:
            parts: list[str] = []
            for i, col in enumerate(self._columns):
                val = cells[i] if i < len(cells) else ""
                parts.append(" " + self._align_cell(val, widths[i], col.align) + " ")
            return "|" + "|".join(parts) + "|"

        # Header
        lines.append(md_row([c.name for c in self._columns]))

        # Separator row
        sep_parts: list[str] = []
        for i, col in enumerate(self._columns):
            dash = "-" * widths[i]
            if col.align == "right":
                sep_parts.append(" " + dash[:-1] + ": ")
            elif col.align == "center":
                sep_parts.append(":" + dash[:-1] + ": ")
            else:
                sep_parts.append(" " + dash + " ")
        lines.append("|" + "|".join(sep_parts) + "|")

        # Data rows
        for row in self._rows:
            if isinstance(row, _SeparatorRow):
                continue
            lines.append(md_row(row))

        return "\n".join(lines)
