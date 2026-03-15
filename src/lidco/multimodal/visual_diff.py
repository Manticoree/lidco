"""Visual diff rendering using Rich tables and colored text."""

from __future__ import annotations

import difflib
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from rich.table import Table
    from rich.text import Text
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

_ADDED_STYLE = "green"
_REMOVED_STYLE = "red"
_CONTEXT_STYLE = "dim"
_HEADER_STYLE = "bold cyan"


def _plain_side_by_side(old_lines: list[str], new_lines: list[str], filename: str) -> str:
    """Fallback plain-text side-by-side diff when Rich is unavailable."""
    max_lines = max(len(old_lines), len(new_lines))
    width = 40
    rows = [f"{'OLD':<{width}}  {'NEW':<{width}}"]
    rows.append("-" * (width * 2 + 2))
    for i in range(max_lines):
        left = old_lines[i].rstrip() if i < len(old_lines) else ""
        right = new_lines[i].rstrip() if i < len(new_lines) else ""
        rows.append(f"{left:<{width}}  {right:<{width}}")
    return "\n".join(rows)


class VisualDiffer:
    """Rich-based side-by-side and inline diff renderer."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def side_by_side(self, old_text: str, new_text: str, filename: str = "") -> "Table | str":
        """Return a Rich ``Table`` (or plain string fallback) with two columns."""
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        if not _HAS_RICH:
            return _plain_side_by_side(old_lines, new_lines, filename)

        table = Table(
            title=f"Visual diff: {filename}" if filename else "Visual diff",
            show_lines=True,
            expand=True,
        )
        table.add_column("Before", style=_REMOVED_STYLE, ratio=1)
        table.add_column("After", style=_ADDED_STYLE, ratio=1)

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            left_chunk = old_lines[i1:i2]
            right_chunk = new_lines[j1:j2]
            max_len = max(len(left_chunk), len(right_chunk))
            for idx in range(max_len):
                left_cell = left_chunk[idx] if idx < len(left_chunk) else ""
                right_cell = right_chunk[idx] if idx < len(right_chunk) else ""

                if tag == "equal":
                    table.add_row(
                        Text(left_cell, style=_CONTEXT_STYLE),
                        Text(right_cell, style=_CONTEXT_STYLE),
                    )
                elif tag == "replace":
                    table.add_row(
                        Text(left_cell, style=_REMOVED_STYLE),
                        Text(right_cell, style=_ADDED_STYLE),
                    )
                elif tag == "delete":
                    table.add_row(Text(left_cell, style=_REMOVED_STYLE), Text(""))
                elif tag == "insert":
                    table.add_row(Text(""), Text(right_cell, style=_ADDED_STYLE))

        return table

    def inline_rich(self, diff_text: str) -> "Text | str":
        """Color ``+``/``-`` lines in a unified-diff string using Rich ``Text``."""
        if not _HAS_RICH:
            return diff_text

        rich_text = Text()
        for line in diff_text.splitlines(keepends=True):
            if line.startswith("+") and not line.startswith("+++"):
                rich_text.append(line, style=_ADDED_STYLE)
            elif line.startswith("-") and not line.startswith("---"):
                rich_text.append(line, style=_REMOVED_STYLE)
            elif line.startswith("@@"):
                rich_text.append(line, style=_HEADER_STYLE)
            else:
                rich_text.append(line, style=_CONTEXT_STYLE)
        return rich_text

    def render_file_diff(self, file_path: str | Path) -> "Table | Text | str":
        """Run ``git diff HEAD <file>`` and render the result visually."""
        path = Path(file_path)
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD", "--", str(path)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            diff_output = result.stdout
        except subprocess.TimeoutExpired:
            return "git diff timed out."
        except Exception as exc:
            return f"git diff failed: {exc}"

        if not diff_output.strip():
            return f"No diff for `{path}` (clean or untracked)."

        return self.inline_rich(diff_output)

    def diff_strings(self, old_text: str, new_text: str) -> str:
        """Return a unified diff string between *old_text* and *new_text*."""
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff = difflib.unified_diff(old_lines, new_lines, fromfile="before", tofile="after")
        return "".join(diff)
