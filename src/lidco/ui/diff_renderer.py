"""Diff Visualization — unified and side-by-side diff rendering (Q177)."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class WordDiff:
    """A word-level difference."""

    kind: str  # "add", "remove", "equal"
    text: str


def _word_level_diff(old_line: str, new_line: str) -> list[WordDiff]:
    """Compute word-level differences between two lines."""
    old_words = old_line.split()
    new_words = new_line.split()
    matcher = difflib.SequenceMatcher(None, old_words, new_words)
    result: list[WordDiff] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result.append(WordDiff("equal", " ".join(old_words[i1:i2])))
        elif tag == "replace":
            result.append(WordDiff("remove", " ".join(old_words[i1:i2])))
            result.append(WordDiff("add", " ".join(new_words[j1:j2])))
        elif tag == "delete":
            result.append(WordDiff("remove", " ".join(old_words[i1:i2])))
        elif tag == "insert":
            result.append(WordDiff("add", " ".join(new_words[j1:j2])))
    return result


def _fold_unchanged(lines: list[str], context: int = 3) -> list[str]:
    """Fold unchanged regions, keeping *context* lines around changes."""
    if context < 0:
        return list(lines)

    # Mark lines that are changes
    change_indices: set[int] = set()
    for i, line in enumerate(lines):
        if line.startswith("+") or line.startswith("-"):
            # Skip the --- / +++ header lines
            if line.startswith("---") or line.startswith("+++"):
                change_indices.add(i)
                continue
            change_indices.add(i)

    if not change_indices:
        return list(lines)

    # Mark context lines around changes
    visible: set[int] = set()
    for idx in change_indices:
        for offset in range(-context, context + 1):
            pos = idx + offset
            if 0 <= pos < len(lines):
                visible.add(pos)

    # Also always show header lines (@@, ---, +++)
    for i, line in enumerate(lines):
        if line.startswith("@@") or line.startswith("---") or line.startswith("+++"):
            visible.add(i)

    result: list[str] = []
    last_shown = -1
    for i in range(len(lines)):
        if i in visible:
            if last_shown >= 0 and i - last_shown > 1:
                skipped = i - last_shown - 1
                result.append(f"... ({skipped} lines folded) ...")
            result.append(lines[i])
            last_shown = i

    if last_shown < len(lines) - 1 and last_shown >= 0:
        skipped = len(lines) - 1 - last_shown
        result.append(f"... ({skipped} lines folded) ...")

    return result


class DiffRenderer:
    """Render diffs in unified or side-by-side format with word-level highlighting."""

    def __init__(self, context_lines: int = 3) -> None:
        self._context_lines = context_lines

    def render_unified(
        self, old_text: str, new_text: str, filename: str = ""
    ) -> str:
        """Render a unified diff between old_text and new_text."""
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        from_name = f"a/{filename}" if filename else "a/old"
        to_name = f"b/{filename}" if filename else "b/new"

        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=from_name,
                tofile=to_name,
                n=self._context_lines,
            )
        )

        if not diff:
            return ""

        # Strip trailing newlines from each diff line for clean output
        result = [line.rstrip("\n") for line in diff]
        return "\n".join(_fold_unchanged(result, self._context_lines))

    def render_side_by_side(
        self, old_text: str, new_text: str, width: int = 80
    ) -> str:
        """Render a side-by-side diff. Each side gets (width - 3) // 2 columns."""
        col_width = (width - 3) // 2  # 3 chars for " | " separator

        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        rows: list[str] = []

        # Header
        left_hdr = "OLD".center(col_width)
        right_hdr = "NEW".center(col_width)
        rows.append(f"{left_hdr} | {right_hdr}")
        rows.append("-" * col_width + "-+-" + "-" * col_width)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    left = old_lines[i1 + k][:col_width].ljust(col_width)
                    right = new_lines[j1 + k][:col_width].ljust(col_width)
                    rows.append(f"{left} | {right}")
            elif tag == "replace":
                max_len = max(i2 - i1, j2 - j1)
                for k in range(max_len):
                    left = (
                        old_lines[i1 + k][:col_width].ljust(col_width)
                        if i1 + k < i2
                        else " " * col_width
                    )
                    right = (
                        new_lines[j1 + k][:col_width].ljust(col_width)
                        if j1 + k < j2
                        else " " * col_width
                    )
                    rows.append(f"{left} | {right}")
            elif tag == "delete":
                for k in range(i2 - i1):
                    left = old_lines[i1 + k][:col_width].ljust(col_width)
                    right = " " * col_width
                    rows.append(f"{left} | {right}")
            elif tag == "insert":
                for k in range(j2 - j1):
                    left = " " * col_width
                    right = new_lines[j1 + k][:col_width].ljust(col_width)
                    rows.append(f"{left} | {right}")

        return "\n".join(rows)

    def word_diff(self, old_line: str, new_line: str) -> list[WordDiff]:
        """Return word-level diff between two single lines."""
        return _word_level_diff(old_line, new_line)

    def render_word_diff(self, old_line: str, new_line: str) -> str:
        """Render word-level diff as a marked-up string."""
        parts: list[str] = []
        for wd in _word_level_diff(old_line, new_line):
            if wd.kind == "equal":
                parts.append(wd.text)
            elif wd.kind == "add":
                parts.append(f"{{+{wd.text}+}}")
            elif wd.kind == "remove":
                parts.append(f"[-{wd.text}-]")
        return " ".join(parts)
