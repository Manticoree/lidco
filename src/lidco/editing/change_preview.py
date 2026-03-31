"""ChangePreview — generate diff previews between old and new content.

Stdlib only — uses difflib.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class PreviewLine:
    """A single line in a diff preview."""

    line_number: int
    content: str
    change_type: str  # "add", "remove", "context"


class ChangePreview:
    """Generate and format diff previews."""

    def preview(
        self, old_content: str, new_content: str, context_lines: int = 3
    ) -> list[PreviewLine]:
        """Produce a list of PreviewLine objects from a unified diff."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines, new_lines, lineterm="", n=context_lines
        )

        result: list[PreviewLine] = []
        line_num = 0

        for line in diff:
            # Skip diff headers
            if line.startswith("---") or line.startswith("+++"):
                continue
            if line.startswith("@@"):
                # Parse hunk header to get line number
                try:
                    parts = line.split("+")[1]
                    line_num = int(parts.split(",")[0]) - 1
                except (IndexError, ValueError):
                    pass
                continue

            content = line[1:] if len(line) > 0 else ""
            # Strip trailing newline from content for cleaner output
            content = content.rstrip("\n").rstrip("\r")

            if line.startswith("+"):
                line_num += 1
                result.append(PreviewLine(line_number=line_num, content=content, change_type="add"))
            elif line.startswith("-"):
                result.append(PreviewLine(line_number=line_num, content=content, change_type="remove"))
            else:
                line_num += 1
                result.append(PreviewLine(line_number=line_num, content=content, change_type="context"))

        return result

    def format_preview(self, lines: list[PreviewLine]) -> str:
        """Format PreviewLine list into a string with +/- prefixes."""
        output: list[str] = []
        for pl in lines:
            if pl.change_type == "add":
                prefix = "+"
            elif pl.change_type == "remove":
                prefix = "-"
            else:
                prefix = " "
            output.append(f"{prefix} {pl.content}")
        return "\n".join(output)

    def stats(self, old_content: str, new_content: str) -> dict:
        """Return addition/deletion/unchanged line counts."""
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        additions = 0
        deletions = 0
        unchanged = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                unchanged += i2 - i1
            elif tag == "replace":
                deletions += i2 - i1
                additions += j2 - j1
            elif tag == "insert":
                additions += j2 - j1
            elif tag == "delete":
                deletions += i2 - i1

        return {
            "additions": additions,
            "deletions": deletions,
            "unchanged": unchanged,
        }

    def has_changes(self, old_content: str, new_content: str) -> bool:
        """Return True if old and new content differ."""
        return old_content != new_content
