"""MemoryTracker — track memory usage over time."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator, Optional


def _default_memory_fn() -> int:
    """Best-effort RSS estimate using platform APIs, falling back to sys."""
    try:
        import resource  # type: ignore[import-not-found]
        # Unix: maxrss in KB on Linux, bytes on macOS
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return usage  # bytes
        return usage * 1024  # KB -> bytes
    except (ImportError, AttributeError):
        pass
    # Windows / fallback: rough estimate via sys.getsizeof on a few objects
    import gc
    total = 0
    for obj in gc.get_objects()[:500]:
        try:
            total += sys.getsizeof(obj)
        except (TypeError, ReferenceError):
            pass
    return total


@dataclass
class MemorySnapshot:
    """A single memory measurement."""

    label: str
    timestamp: float
    rss_bytes: int
    delta_bytes: int


class MemoryTracker:
    """Track memory usage via snapshots."""

    def __init__(self, get_memory_fn: Optional[Callable[[], int]] = None) -> None:
        self._get_memory = get_memory_fn or _default_memory_fn
        self._snapshots: list[MemorySnapshot] = []

    def snapshot(self, label: str = "") -> MemorySnapshot:
        """Take a memory snapshot."""
        rss = self._get_memory()
        prev_rss = self._snapshots[-1].rss_bytes if self._snapshots else 0
        snap = MemorySnapshot(
            label=label,
            timestamp=time.time(),
            rss_bytes=rss,
            delta_bytes=rss - prev_rss,
        )
        self._snapshots.append(snap)
        return snap

    @contextmanager
    def track(self, label: str) -> Iterator[None]:
        """Context manager that records before/after snapshots."""
        self.snapshot(f"{label}:before")
        try:
            yield
        finally:
            self.snapshot(f"{label}:after")

    @property
    def snapshots(self) -> list[MemorySnapshot]:
        """All recorded snapshots."""
        return list(self._snapshots)

    def peak(self) -> Optional[MemorySnapshot]:
        """Snapshot with highest RSS."""
        if not self._snapshots:
            return None
        return max(self._snapshots, key=lambda s: s.rss_bytes)

    def growth(self, since_label: Optional[str] = None) -> int:
        """Bytes grown since a labeled snapshot (or from the first)."""
        if not self._snapshots:
            return 0
        if since_label is not None:
            for s in self._snapshots:
                if s.label == since_label:
                    return self._snapshots[-1].rss_bytes - s.rss_bytes
            return 0
        return self._snapshots[-1].rss_bytes - self._snapshots[0].rss_bytes

    def format_report(self) -> str:
        """Human-readable report with KB/MB formatting."""
        if not self._snapshots:
            return "No snapshots recorded."
        lines = ["Memory Report", "=" * 50]
        for s in self._snapshots:
            size_str = _fmt_bytes(s.rss_bytes)
            delta_str = _fmt_bytes(s.delta_bytes)
            sign = "+" if s.delta_bytes >= 0 else ""
            lines.append(f"  {s.label or '(unlabeled)':30s}  {size_str:>10s}  ({sign}{delta_str})")
        peak = self.peak()
        if peak:
            lines.append(f"\nPeak: {_fmt_bytes(peak.rss_bytes)} ({peak.label})")
        total_growth = self.growth()
        lines.append(f"Total growth: {_fmt_bytes(total_growth)}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Remove all snapshots."""
        self._snapshots.clear()


def _fmt_bytes(b: int) -> str:
    """Format byte count as human readable."""
    ab = abs(b)
    if ab < 1024:
        return f"{b} B"
    if ab < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b / (1024 * 1024):.1f} MB"
