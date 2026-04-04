"""MemoryProfiler — track memory allocations; find leaks; object count trends."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class MemorySnapshot:
    """A snapshot of memory state at a point in time."""

    timestamp: float
    total_bytes: int
    allocations: dict[str, int] = field(default_factory=dict)
    peak_bytes: int = 0


class MemoryProfiler:
    """Track memory allocations; find leaks; object count trends; per-function."""

    def __init__(self) -> None:
        self._allocations: dict[str, int] = {}
        self._snapshots: list[MemorySnapshot] = []
        self._peak: int = 0
        self._allocation_history: dict[str, list[int]] = {}

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def snapshot(self, label: str = "") -> MemorySnapshot:
        """Record current state (simulated)."""
        total = sum(self._allocations.values())
        if total > self._peak:
            self._peak = total
        snap = MemorySnapshot(
            timestamp=time.time(),
            total_bytes=total,
            allocations=dict(self._allocations),
            peak_bytes=self._peak,
        )
        self._snapshots.append(snap)
        return snap

    def record_allocation(self, source: str, bytes_: int) -> None:
        """Record an allocation from *source*."""
        self._allocations[source] = self._allocations.get(source, 0) + bytes_
        history = self._allocation_history.setdefault(source, [])
        history.append(self._allocations[source])
        total = sum(self._allocations.values())
        if total > self._peak:
            self._peak = total

    def record_deallocation(self, source: str, bytes_: int) -> None:
        """Record a deallocation from *source*."""
        current = self._allocations.get(source, 0)
        new_val = max(current - bytes_, 0)
        if new_val == 0:
            self._allocations.pop(source, None)
        else:
            self._allocations[source] = new_val
        history = self._allocation_history.setdefault(source, [])
        history.append(self._allocations.get(source, 0))

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def detect_leaks(self, threshold_bytes: int = 1024) -> list[dict]:
        """Sources with growing allocations above *threshold_bytes*."""
        leaks: list[dict] = []
        for source, history in self._allocation_history.items():
            if len(history) < 2:
                continue
            current = self._allocations.get(source, 0)
            growth = history[-1] - history[0]
            if current >= threshold_bytes or growth >= threshold_bytes:
                leaks.append({
                    "source": source,
                    "growth_bytes": growth,
                    "current_bytes": self._allocations.get(source, 0),
                })
        return leaks

    def top_allocators(self, limit: int = 10) -> list[tuple[str, int]]:
        """Top sources by current allocated bytes."""
        items = sorted(
            self._allocations.items(), key=lambda x: x[1], reverse=True
        )
        return items[:limit]

    def snapshots(self) -> list[MemorySnapshot]:
        """Return all recorded snapshots."""
        return list(self._snapshots)

    def growth_trend(self) -> list[dict]:
        """Bytes over time from snapshots."""
        return [
            {
                "timestamp": s.timestamp,
                "total_bytes": s.total_bytes,
                "peak_bytes": s.peak_bytes,
            }
            for s in self._snapshots
        ]

    def summary(self) -> dict:
        """Summary of memory profiler state."""
        return {
            "active_sources": len(self._allocations),
            "total_bytes": sum(self._allocations.values()),
            "peak_bytes": self._peak,
            "snapshots": len(self._snapshots),
        }
