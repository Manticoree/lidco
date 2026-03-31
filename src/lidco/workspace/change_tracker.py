"""Change tracker for workspace files — Q127."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileChange:
    path: str
    kind: str  # "added"/"modified"/"deleted"
    old_content: str = ""
    new_content: str = ""


class ChangeTracker:
    """Track file changes with undo support."""

    def __init__(self) -> None:
        self._changes: list[FileChange] = []

    def record(self, change: FileChange) -> None:
        self._changes.append(change)

    def changes(self) -> list[FileChange]:
        return list(self._changes)

    def changed_paths(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for c in self._changes:
            if c.path not in seen:
                seen.add(c.path)
                result.append(c.path)
        return result

    def undo(self, path: str) -> Optional[FileChange]:
        """Pop the last change for *path*."""
        for i in range(len(self._changes) - 1, -1, -1):
            if self._changes[i].path == path:
                return self._changes.pop(i)
        return None

    def clear(self) -> None:
        self._changes.clear()

    def summary(self) -> dict:
        counts: dict[str, int] = {"added": 0, "modified": 0, "deleted": 0}
        for c in self._changes:
            if c.kind in counts:
                counts[c.kind] += 1
        return counts
