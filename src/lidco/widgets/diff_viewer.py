"""DiffViewer widget — side-by-side diff, hunk navigation, accept/reject."""
from __future__ import annotations

from dataclasses import dataclass, field


from lidco.widgets.framework import Widget


@dataclass
class DiffHunk:
    """A single diff hunk with accept/reject status."""

    id: int
    old_start: int
    old_lines: list[str] = field(default_factory=list)
    new_start: int = 0
    new_lines: list[str] = field(default_factory=list)
    status: str = "pending"  # "pending" | "accepted" | "rejected"


class DiffViewer(Widget):
    """Diff viewer with hunk-level accept/reject."""

    def __init__(self, old_content: str = "", new_content: str = "") -> None:
        super().__init__(id="diff-viewer", title="Diff Viewer")
        self._hunks: list[DiffHunk] = []
        self._old_content = old_content
        self._new_content = new_content
        self._cursor = 0
        if old_content or new_content:
            self.set_contents(old_content, new_content)

    def set_contents(self, old_content: str, new_content: str) -> None:
        """Compute diff hunks from old and new content."""
        self._old_content = old_content
        self._new_content = new_content
        self._hunks = []
        self._cursor = 0

        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        # Simple diff: find contiguous blocks of changes
        hunk_id = 0
        i = 0
        j = 0
        max_len = max(len(old_lines), len(new_lines))

        while i < max_len or j < max_len:
            # Skip matching lines
            if i < len(old_lines) and j < len(new_lines) and old_lines[i] == new_lines[j]:
                i += 1
                j += 1
                continue

            # Collect differing block
            old_block: list[str] = []
            new_block: list[str] = []
            old_start = i + 1
            new_start = j + 1

            while i < len(old_lines) or j < len(new_lines):
                if i < len(old_lines) and j < len(new_lines) and old_lines[i] == new_lines[j]:
                    break
                if i < len(old_lines):
                    old_block.append(old_lines[i])
                    i += 1
                if j < len(new_lines):
                    new_block.append(new_lines[j])
                    j += 1

            if old_block or new_block:
                self._hunks.append(DiffHunk(
                    id=hunk_id,
                    old_start=old_start,
                    old_lines=old_block,
                    new_start=new_start,
                    new_lines=new_block,
                ))
                hunk_id += 1

    def hunks(self) -> list[DiffHunk]:
        return list(self._hunks)

    def _find_hunk(self, hunk_id: int) -> DiffHunk | None:
        for h in self._hunks:
            if h.id == hunk_id:
                return h
        return None

    def accept_hunk(self, hunk_id: int) -> bool:
        h = self._find_hunk(hunk_id)
        if h is None:
            return False
        h.status = "accepted"
        return True

    def reject_hunk(self, hunk_id: int) -> bool:
        h = self._find_hunk(hunk_id)
        if h is None:
            return False
        h.status = "rejected"
        return True

    def next_hunk(self) -> DiffHunk | None:
        """Return the next pending hunk after cursor."""
        pending = [h for h in self._hunks if h.status == "pending"]
        if not pending:
            return None
        # Find first pending after cursor
        for h in pending:
            if h.id >= self._cursor:
                self._cursor = h.id + 1
                return h
        # Wrap around
        self._cursor = pending[0].id + 1
        return pending[0]

    def prev_hunk(self) -> DiffHunk | None:
        """Return the previous pending hunk before cursor."""
        pending = [h for h in self._hunks if h.status == "pending"]
        if not pending:
            return None
        # Find last pending before cursor
        for h in reversed(pending):
            if h.id < self._cursor:
                self._cursor = h.id
                return h
        # Wrap to end
        self._cursor = pending[-1].id
        return pending[-1]

    def apply(self) -> str:
        """Apply accepted hunks to old content, return result."""
        old_lines = self._old_content.splitlines()
        # Build a mapping of old line ranges to new content for accepted hunks
        # For rejected hunks, keep old lines; for accepted, use new lines
        result_lines: list[str] = []
        old_idx = 0

        for hunk in sorted(self._hunks, key=lambda h: h.old_start):
            hunk_old_start = hunk.old_start - 1  # 1-based to 0-based

            # Copy unchanged lines before this hunk
            while old_idx < hunk_old_start and old_idx < len(old_lines):
                result_lines.append(old_lines[old_idx])
                old_idx += 1

            if hunk.status == "accepted":
                # Use new lines
                result_lines.extend(hunk.new_lines)
            else:
                # Keep old lines (pending or rejected)
                result_lines.extend(hunk.old_lines)

            old_idx = hunk_old_start + len(hunk.old_lines)

        # Copy remaining old lines
        while old_idx < len(old_lines):
            result_lines.append(old_lines[old_idx])
            old_idx += 1

        return "\n".join(result_lines)

    def stats(self) -> dict:
        accepted = sum(1 for h in self._hunks if h.status == "accepted")
        rejected = sum(1 for h in self._hunks if h.status == "rejected")
        pending = sum(1 for h in self._hunks if h.status == "pending")
        return {"accepted": accepted, "rejected": rejected, "pending": pending, "total": len(self._hunks)}

    def render(self) -> str:
        s = self.stats()
        return (
            f"[DiffViewer] {s['total']} hunks: "
            f"{s['accepted']} accepted, {s['rejected']} rejected, {s['pending']} pending"
        )
