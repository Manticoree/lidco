"""Edit Diff — line-level and unified diff utilities using difflib.

Stdlib only — no external deps.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class DiffLine:
    """A single line in a diff output."""
    tag: str    # '+', '-', or ' '
    content: str


class EditDiff:
    """Line-level diff utilities."""

    def diff_lines(self, old: str, new: str) -> list[DiffLine]:
        """Compute line-level diff between old and new text.

        Returns list of DiffLine with tags: '+' added, '-' removed, ' ' unchanged.
        """
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        sm = difflib.SequenceMatcher(None, old_lines, new_lines)
        result: list[DiffLine] = []
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal":
                for line in old_lines[i1:i2]:
                    result.append(DiffLine(tag=" ", content=line))
            elif op == "replace":
                for line in old_lines[i1:i2]:
                    result.append(DiffLine(tag="-", content=line))
                for line in new_lines[j1:j2]:
                    result.append(DiffLine(tag="+", content=line))
            elif op == "delete":
                for line in old_lines[i1:i2]:
                    result.append(DiffLine(tag="-", content=line))
            elif op == "insert":
                for line in new_lines[j1:j2]:
                    result.append(DiffLine(tag="+", content=line))
        return result

    def unified_diff(
        self, old: str, new: str, filename: str = "", context: int = 3
    ) -> str:
        """Generate unified diff format string."""
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        fromfile = f"a/{filename}" if filename else "a/original"
        tofile = f"b/{filename}" if filename else "b/modified"
        diff = difflib.unified_diff(
            old_lines, new_lines, fromfile=fromfile, tofile=tofile, n=context
        )
        return "".join(diff)

    def stats(self, old: str, new: str) -> dict[str, int]:
        """Return diff statistics: added, removed, unchanged line counts."""
        diff_lines = self.diff_lines(old, new)
        added = sum(1 for dl in diff_lines if dl.tag == "+")
        removed = sum(1 for dl in diff_lines if dl.tag == "-")
        unchanged = sum(1 for dl in diff_lines if dl.tag == " ")
        return {"added": added, "removed": removed, "unchanged": unchanged}

    def is_identical(self, old: str, new: str) -> bool:
        """Return True if old and new are identical."""
        return old == new
