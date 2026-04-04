"""Branch cleanup utilities.

Identifies stale, merged, and orphaned branches and supports bulk deletion
with a protected-branches safeguard.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class _BranchInfo:
    name: str
    last_activity: float  # epoch seconds
    merged: bool = False


@dataclass
class BranchCleanup:
    """Track branches and find candidates for cleanup."""

    _branches: dict[str, _BranchInfo] = field(default_factory=dict)
    _protected: set[str] = field(default_factory=lambda: {"main", "master"})

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_branch(self, name: str, last_activity: float, merged: bool = False) -> None:
        """Register a branch for tracking."""
        self._branches[name] = _BranchInfo(
            name=name, last_activity=last_activity, merged=merged
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def stale(self, days: int = 30) -> list[str]:
        """Return branch names with no activity in the last *days*."""
        cutoff = time.time() - days * 86400
        return [
            b.name
            for b in self._branches.values()
            if b.last_activity < cutoff and b.name not in self._protected
        ]

    def merged(self) -> list[str]:
        """Return branch names already merged (excluding protected)."""
        return [
            b.name
            for b in self._branches.values()
            if b.merged and b.name not in self._protected
        ]

    def orphaned(self) -> list[str]:
        """Return branches that are both stale (>90 days) and not merged."""
        cutoff = time.time() - 90 * 86400
        return [
            b.name
            for b in self._branches.values()
            if b.last_activity < cutoff
            and not b.merged
            and b.name not in self._protected
        ]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def bulk_delete(self, names: list[str]) -> int:
        """Delete branches by name, skipping protected ones.  Return count deleted."""
        count = 0
        for n in names:
            if n in self._protected:
                continue
            if n in self._branches:
                del self._branches[n]
                count += 1
        return count

    def protected(self, names: list[str]) -> None:
        """Mark branch names as protected (they will never be deleted)."""
        self._protected.update(names)
