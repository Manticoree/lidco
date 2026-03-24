"""DiffEngine — preview unified diffs and selectively apply hunks."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path

from .hunk import Hunk


@dataclass
class DiffPreview:
    path: str
    original: str
    new_content: str
    hunks: list[Hunk]

    @property
    def has_changes(self) -> bool:
        return len(self.hunks) > 0

    def apply(self, accepted_indices: set[int]) -> str:
        """Apply only the accepted hunks. Rejected hunks keep original lines."""
        if not self.hunks:
            return self.new_content

        original_lines = self.original.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)

        # If all accepted, return new content directly
        if accepted_indices == set(range(len(self.hunks))):
            return self.new_content

        # If none accepted, return original
        if not accepted_indices:
            return self.original

        # Partial apply: build result hunk by hunk
        # Use difflib to re-apply selectively
        result = list(original_lines)
        offset = 0

        for hunk in self.hunks:
            if hunk.index not in accepted_indices:
                continue
            # Parse header to find line numbers
            # @@ -start,count +start,count @@
            header = hunk.header
            try:
                parts = header.split("@@")[1].strip().split()
                old_range = parts[0][1:]  # remove '-'
                new_range = parts[1][1:]  # remove '+'
                old_start = int(old_range.split(",")[0]) - 1
                old_count = int(old_range.split(",")[1]) if "," in old_range else 1
                new_added = [l[1:] for l in hunk.lines if l.startswith("+")]
                actual_start = old_start + offset
                result[actual_start: actual_start + old_count] = [l if l.endswith("\n") else l + "\n" for l in new_added]
                offset += len(new_added) - old_count
            except (IndexError, ValueError):
                pass

        return "".join(result)


class DiffEngine:
    """Generates diff previews with per-hunk accept/reject."""

    def preview(self, path: str, original: str, new_content: str) -> DiffPreview:
        """Generate a DiffPreview splitting the unified diff into Hunk objects."""
        diff_lines = list(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )

        hunks = _parse_hunks(diff_lines)
        return DiffPreview(path=path, original=original, new_content=new_content, hunks=hunks)


def _parse_hunks(diff_lines: list[str]) -> list[Hunk]:
    hunks: list[Hunk] = []
    current_header: str | None = None
    current_lines: list[str] = []
    hunk_index = 0

    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            if current_header is not None:
                hunks.append(Hunk(index=hunk_index, header=current_header, lines=current_lines))
                hunk_index += 1
            current_header = line
            current_lines = []
        elif current_header is not None:
            current_lines.append(line)

    if current_header is not None:
        hunks.append(Hunk(index=hunk_index, header=current_header, lines=current_lines))

    return hunks
