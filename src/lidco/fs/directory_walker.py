"""Q132: BFS directory walker with ignore patterns."""
from __future__ import annotations

import fnmatch
import os
from collections import deque
from dataclasses import dataclass, field

_DEFAULT_IGNORES = [
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".mypy_cache", ".pytest_cache",
]


@dataclass
class WalkEntry:
    path: str
    is_dir: bool
    size: int = 0
    depth: int = 0


class DirectoryWalker:
    """BFS directory walker with configurable ignore patterns."""

    def __init__(self, ignore_patterns: list[str] | None = None) -> None:
        self._ignores = list(ignore_patterns) if ignore_patterns is not None else list(_DEFAULT_IGNORES)

    def walk(
        self,
        root: str,
        listdir_fn=None,
        isdir_fn=None,
        getsize_fn=None,
    ) -> list[WalkEntry]:
        """Return all WalkEntry objects under *root* (BFS)."""
        listdir = listdir_fn or os.listdir
        isdir = isdir_fn or os.path.isdir
        getsize = getsize_fn or (lambda p: os.path.getsize(p) if not os.path.isdir(p) else 0)

        entries: list[WalkEntry] = []
        queue: deque[tuple[str, int]] = deque()
        queue.append((root, 0))

        while queue:
            current, depth = queue.popleft()
            try:
                children = listdir(current)
            except (PermissionError, OSError):
                continue

            for name in sorted(children):
                if self._is_ignored(name):
                    continue
                child_path = os.path.join(current, name)
                child_is_dir = isdir(child_path)
                size = 0 if child_is_dir else getsize(child_path)
                entry = WalkEntry(
                    path=child_path,
                    is_dir=child_is_dir,
                    size=size,
                    depth=depth + 1,
                )
                entries.append(entry)
                if child_is_dir:
                    queue.append((child_path, depth + 1))

        return entries

    def files_only(self, entries: list[WalkEntry]) -> list[WalkEntry]:
        return [e for e in entries if not e.is_dir]

    def dirs_only(self, entries: list[WalkEntry]) -> list[WalkEntry]:
        return [e for e in entries if e.is_dir]

    def max_depth(self, entries: list[WalkEntry], depth: int) -> list[WalkEntry]:
        return [e for e in entries if e.depth <= depth]

    def total_size(self, entries: list[WalkEntry]) -> int:
        return sum(e.size for e in entries)

    # --- internals -----------------------------------------------------------

    def _is_ignored(self, name: str) -> bool:
        for pat in self._ignores:
            if fnmatch.fnmatch(name, pat):
                return True
        return False
