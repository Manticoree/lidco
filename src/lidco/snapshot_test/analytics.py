"""
Snapshot Analytics — stats, churn rate, size trends, stale snapshots, orphaned files.

Task 1680.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lidco.snapshot_test.manager import SnapshotManager


@dataclass(frozen=True)
class SnapshotStats:
    """Aggregate statistics for the snapshot directory."""

    total_snapshots: int
    total_size_bytes: int
    avg_size_bytes: float
    largest_name: str
    largest_size: int
    smallest_name: str
    smallest_size: int


@dataclass(frozen=True)
class ChurnEntry:
    """Churn info for one snapshot."""

    name: str
    update_count: int
    last_updated: float
    age_days: float


@dataclass(frozen=True)
class ChurnReport:
    """Churn rate across all snapshots."""

    entries: list[ChurnEntry]
    avg_updates: float
    most_churned: str
    least_churned: str


@dataclass(frozen=True)
class SizeTrendEntry:
    """Size record for a single snapshot."""

    name: str
    size_bytes: int
    updated_at: float


@dataclass(frozen=True)
class StaleSnapshot:
    """A snapshot not updated for longer than the threshold."""

    name: str
    last_updated: float
    age_days: float


class SnapshotAnalytics:
    """Analyze snapshots: stats, churn, size trends, stale & orphaned detection."""

    DEFAULT_STALE_DAYS = 90

    def __init__(self, manager: SnapshotManager) -> None:
        self._manager = manager

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> SnapshotStats:
        """Compute aggregate snapshot statistics."""
        names = self._manager.list_snapshots()
        if not names:
            return SnapshotStats(
                total_snapshots=0,
                total_size_bytes=0,
                avg_size_bytes=0.0,
                largest_name="",
                largest_size=0,
                smallest_name="",
                smallest_size=0,
            )

        sizes: list[tuple[str, int]] = []
        for n in names:
            rec = self._manager.read(n)
            if rec:
                sizes.append((n, rec.meta.size_bytes))

        if not sizes:
            return SnapshotStats(
                total_snapshots=0, total_size_bytes=0, avg_size_bytes=0.0,
                largest_name="", largest_size=0, smallest_name="", smallest_size=0,
            )

        total = sum(s for _, s in sizes)
        largest = max(sizes, key=lambda x: x[1])
        smallest = min(sizes, key=lambda x: x[1])

        return SnapshotStats(
            total_snapshots=len(sizes),
            total_size_bytes=total,
            avg_size_bytes=total / len(sizes),
            largest_name=largest[0],
            largest_size=largest[1],
            smallest_name=smallest[0],
            smallest_size=smallest[1],
        )

    # ------------------------------------------------------------------
    # Churn
    # ------------------------------------------------------------------

    def churn(self) -> ChurnReport:
        """Compute churn report. Update count is approximated from meta timestamps."""
        names = self._manager.list_snapshots()
        now = time.time()
        entries: list[ChurnEntry] = []

        for n in names:
            rec = self._manager.read(n)
            if not rec:
                continue
            meta = rec.meta
            age = (now - meta.created_at) / 86400.0
            # Estimate updates: if updated_at differs from created_at, count as at least 1 update
            updates = 0 if meta.updated_at == meta.created_at else 1
            entries.append(ChurnEntry(name=n, update_count=updates, last_updated=meta.updated_at, age_days=age))

        if not entries:
            return ChurnReport(entries=[], avg_updates=0.0, most_churned="", least_churned="")

        avg = sum(e.update_count for e in entries) / len(entries)
        most = max(entries, key=lambda e: e.update_count)
        least = min(entries, key=lambda e: e.update_count)

        return ChurnReport(entries=entries, avg_updates=avg, most_churned=most.name, least_churned=least.name)

    # ------------------------------------------------------------------
    # Size trends
    # ------------------------------------------------------------------

    def size_trends(self) -> list[SizeTrendEntry]:
        """Return per-snapshot size info sorted by size descending."""
        names = self._manager.list_snapshots()
        entries: list[SizeTrendEntry] = []
        for n in names:
            rec = self._manager.read(n)
            if rec:
                entries.append(SizeTrendEntry(name=n, size_bytes=rec.meta.size_bytes, updated_at=rec.meta.updated_at))
        return sorted(entries, key=lambda e: e.size_bytes, reverse=True)

    # ------------------------------------------------------------------
    # Stale snapshots
    # ------------------------------------------------------------------

    def stale_snapshots(self, *, days: float | None = None) -> list[StaleSnapshot]:
        """Find snapshots not updated in more than *days* (default 90)."""
        threshold = days if days is not None else self.DEFAULT_STALE_DAYS
        now = time.time()
        cutoff = now - threshold * 86400.0
        names = self._manager.list_snapshots()
        stale: list[StaleSnapshot] = []
        for n in names:
            rec = self._manager.read(n)
            if rec and rec.meta.updated_at < cutoff:
                age = (now - rec.meta.updated_at) / 86400.0
                stale.append(StaleSnapshot(name=n, last_updated=rec.meta.updated_at, age_days=age))
        return sorted(stale, key=lambda s: s.age_days, reverse=True)

    # ------------------------------------------------------------------
    # Orphaned files
    # ------------------------------------------------------------------

    def orphaned_files(self, known_tests: list[str] | None = None) -> list[str]:
        """Find snapshot names that don't correspond to any known test.

        *known_tests* is a list of snapshot names that are actively used.
        If not provided, returns an empty list (we can't detect orphans without
        a reference set).
        """
        if known_tests is None:
            return []
        all_names = set(self._manager.list_snapshots())
        known = set(known_tests)
        return sorted(all_names - known)
