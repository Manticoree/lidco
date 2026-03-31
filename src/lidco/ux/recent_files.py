"""Q145 Task 859: Recent files tracker."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RecentFile:
    """A tracked file access record."""

    path: str
    last_accessed: float
    access_count: int
    action: str  # "read", "write", or "edit"


class RecentFiles:
    """Tracks recently accessed files with frequency and action filtering."""

    def __init__(self, max_files: int = 50) -> None:
        self._max_files = max_files
        self._files: dict[str, RecentFile] = {}

    def track(self, path: str, action: str = "read") -> None:
        """Record a file access."""
        now = time.time()
        existing = self._files.get(path)
        if existing is not None:
            self._files[path] = RecentFile(
                path=path,
                last_accessed=now,
                access_count=existing.access_count + 1,
                action=action,
            )
        else:
            self._files[path] = RecentFile(
                path=path,
                last_accessed=now,
                access_count=1,
                action=action,
            )
        # Evict oldest if over limit
        if len(self._files) > self._max_files:
            oldest_key = min(self._files, key=lambda k: self._files[k].last_accessed)
            del self._files[oldest_key]

    def recent(self, n: int = 10) -> list[RecentFile]:
        """Return the *n* most recently accessed files."""
        ranked = sorted(
            self._files.values(), key=lambda f: f.last_accessed, reverse=True
        )
        return ranked[:n]

    def frequent(self, n: int = 10) -> list[RecentFile]:
        """Return the *n* most frequently accessed files."""
        ranked = sorted(
            self._files.values(), key=lambda f: f.access_count, reverse=True
        )
        return ranked[:n]

    def by_action(self, action: str) -> list[RecentFile]:
        """Return files filtered by action type."""
        return [f for f in self._files.values() if f.action == action]

    def search(self, pattern: str) -> list[RecentFile]:
        """Return files whose path contains *pattern* (substring match)."""
        p = pattern.lower()
        return [f for f in self._files.values() if p in f.path.lower()]

    def clear(self) -> None:
        """Remove all tracked files."""
        self._files.clear()

    @property
    def size(self) -> int:
        """Number of tracked files."""
        return len(self._files)
