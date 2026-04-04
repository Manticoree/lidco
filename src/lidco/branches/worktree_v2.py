"""Worktree manager v2 — create, remove, list, auto-cleanup.

Pure-Python, stdlib-only implementation that tracks worktrees in-memory
(does not shell out to ``git worktree``).  Real git integration is the
caller's responsibility; this module provides the bookkeeping layer.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Worktree:
    """Represents a single git worktree."""

    branch: str
    path: str
    created_at: float = field(default_factory=time.time)


@dataclass
class WorktreeManagerV2:
    """Manage git worktrees with auto-cleanup and disk tracking."""

    base_dir: str = ".worktrees"
    _worktrees: dict[str, Worktree] = field(default_factory=dict)
    _cache_path: str = ".worktrees/.cache"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, branch: str, path: str | None = None) -> Worktree:
        """Create a new worktree entry.  Returns the ``Worktree``."""
        resolved = path or os.path.join(self.base_dir, branch.replace("/", "_"))
        if resolved in self._worktrees:
            raise ValueError(f"Worktree already exists at '{resolved}'")
        wt = Worktree(branch=branch, path=resolved)
        self._worktrees[resolved] = wt
        return wt

    def remove(self, path: str) -> bool:
        """Remove a worktree by path.  Returns True if it existed."""
        return self._worktrees.pop(path, None) is not None

    def list_worktrees(self) -> list[Worktree]:
        """Return all tracked worktrees."""
        return list(self._worktrees.values())

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def auto_cleanup(self, max_age_seconds: float = 86400) -> int:
        """Remove worktrees older than *max_age_seconds*.  Return count removed."""
        cutoff = time.time() - max_age_seconds
        to_remove = [
            p for p, wt in self._worktrees.items() if wt.created_at < cutoff
        ]
        for p in to_remove:
            del self._worktrees[p]
        return len(to_remove)

    def disk_usage(self) -> dict:
        """Return per-worktree disk usage (bytes).

        Falls back to 0 for paths that do not exist on the filesystem.
        """
        usage: dict[str, int] = {}
        for path, wt in self._worktrees.items():
            total = 0
            p = Path(path)
            if p.is_dir():
                for f in p.rglob("*"):
                    if f.is_file():
                        try:
                            total += f.stat().st_size
                        except OSError:
                            pass
            usage[path] = total
        return usage

    def shared_cache_path(self) -> str:
        """Return the shared object cache directory."""
        return self._cache_path
