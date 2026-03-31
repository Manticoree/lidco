"""Before/After Preview — hunk-level change management (Q177)."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field


@dataclass
class Hunk:
    """A contiguous block of changes."""

    old_start: int  # 1-based line number in old text
    old_lines: list[str]
    new_start: int  # 1-based line number in new text
    new_lines: list[str]
    content: str  # human-readable hunk content

    @property
    def old_count(self) -> int:
        return len(self.old_lines)

    @property
    def new_count(self) -> int:
        return len(self.new_lines)


@dataclass
class PreviewResult:
    """Result of previewing changes."""

    hunks: list[Hunk] = field(default_factory=list)
    old_text: str = ""
    new_text: str = ""

    @property
    def hunk_count(self) -> int:
        return len(self.hunks)

    @property
    def has_changes(self) -> bool:
        return len(self.hunks) > 0


class BeforeAfterPreview:
    """Preview changes as hunks and selectively apply them."""

    def __init__(self, context_lines: int = 3) -> None:
        self._context = context_lines

    def preview(self, old_text: str, new_text: str) -> PreviewResult:
        """Generate a PreviewResult with hunks from diff."""
        if old_text == new_text:
            return PreviewResult(hunks=[], old_text=old_text, new_text=new_text)

        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        hunks: list[Hunk] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue

            old_hunk_lines = old_lines[i1:i2]
            new_hunk_lines = new_lines[j1:j2]

            # Build human-readable content
            content_parts: list[str] = []
            for line in old_hunk_lines:
                content_parts.append(f"- {line}")
            for line in new_hunk_lines:
                content_parts.append(f"+ {line}")

            hunks.append(
                Hunk(
                    old_start=i1 + 1,
                    old_lines=old_hunk_lines,
                    new_start=j1 + 1,
                    new_lines=new_hunk_lines,
                    content="\n".join(content_parts),
                )
            )

        return PreviewResult(hunks=hunks, old_text=old_text, new_text=new_text)

    def accept_hunks(
        self, preview: PreviewResult, selected_indices: list[int]
    ) -> str:
        """Apply only selected hunks and return the resulting text.

        Args:
            preview: The PreviewResult from preview().
            selected_indices: Which hunk indices (0-based) to apply.

        Returns:
            The text with only selected hunks applied.
        """
        if not preview.hunks:
            return preview.old_text

        if not selected_indices:
            return preview.old_text

        old_lines = preview.old_text.splitlines()
        new_lines = preview.new_text.splitlines()

        # Re-compute opcodes to rebuild
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        opcodes = [op for op in matcher.get_opcodes() if op[0] != "equal"]

        # Build a set of accepted hunk indices
        accepted = set(selected_indices)

        # Reconstruct line by line using all opcodes (equal + changes)
        all_opcodes = list(difflib.SequenceMatcher(None, old_lines, new_lines).get_opcodes())
        result: list[str] = []
        change_idx = 0

        for tag, i1, i2, j1, j2 in all_opcodes:
            if tag == "equal":
                result.extend(old_lines[i1:i2])
            else:
                if change_idx in accepted:
                    # Apply the new version
                    result.extend(new_lines[j1:j2])
                else:
                    # Keep the old version
                    result.extend(old_lines[i1:i2])
                change_idx += 1

        return "\n".join(result)

    def reject_all(self, preview: PreviewResult) -> str:
        """Reject all hunks, returning original text."""
        return preview.old_text

    def accept_all(self, preview: PreviewResult) -> str:
        """Accept all hunks, returning new text."""
        if not preview.hunks:
            return preview.old_text
        return self.accept_hunks(
            preview, list(range(len(preview.hunks)))
        )
