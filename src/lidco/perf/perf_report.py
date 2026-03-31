"""PerfReport — compute performance summaries and detect regressions."""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from lidco.perf.timing_profiler import TimingRecord


@dataclass
class PerfSummary:
    """Aggregate performance summary."""

    total_operations: int
    total_time: float
    avg_time: float
    p50: float
    p90: float
    p99: float


class PerfReport:
    """Compute, compare, and format performance summaries."""

    def __init__(self) -> None:
        pass

    def compute(self, records: list[TimingRecord]) -> PerfSummary:
        """Compute a summary with percentiles from timing records."""
        if not records:
            return PerfSummary(
                total_operations=0,
                total_time=0.0,
                avg_time=0.0,
                p50=0.0,
                p90=0.0,
                p99=0.0,
            )
        times = sorted(r.elapsed for r in records)
        total = sum(times)
        return PerfSummary(
            total_operations=len(times),
            total_time=total,
            avg_time=total / len(times),
            p50=self._percentile(times, 50),
            p90=self._percentile(times, 90),
            p99=self._percentile(times, 99),
        )

    def compare(self, before: PerfSummary, after: PerfSummary) -> dict:
        """Compare two summaries, returning deltas and direction."""
        result: dict = {}
        for field_name in ("avg_time", "p50", "p90", "p99", "total_time"):
            bv = getattr(before, field_name)
            av = getattr(after, field_name)
            delta = av - bv
            if bv > 0:
                pct_change = (delta / bv) * 100
            else:
                pct_change = 0.0 if av == 0 else 100.0
            if delta > 0:
                direction = "regression"
            elif delta < 0:
                direction = "improvement"
            else:
                direction = "unchanged"
            result[field_name] = {
                "before": bv,
                "after": av,
                "delta": delta,
                "pct_change": pct_change,
                "direction": direction,
            }
        result["total_operations"] = {
            "before": before.total_operations,
            "after": after.total_operations,
        }
        return result

    def format_summary(self, summary: PerfSummary) -> str:
        """Human-readable summary."""
        return (
            f"Performance Summary\n"
            f"{'=' * 40}\n"
            f"  Operations: {summary.total_operations}\n"
            f"  Total time: {summary.total_time * 1000:.2f} ms\n"
            f"  Avg time:   {summary.avg_time * 1000:.2f} ms\n"
            f"  P50:        {summary.p50 * 1000:.2f} ms\n"
            f"  P90:        {summary.p90 * 1000:.2f} ms\n"
            f"  P99:        {summary.p99 * 1000:.2f} ms"
        )

    def is_regression(self, before: PerfSummary, after: PerfSummary, threshold: float = 0.1) -> bool:
        """Return True if avg_time regressed beyond threshold (fraction)."""
        if before.avg_time == 0:
            return after.avg_time > 0
        return (after.avg_time - before.avg_time) / before.avg_time > threshold

    def trend(self, summaries: list[PerfSummary]) -> str:
        """Determine trend from a series of summaries."""
        if len(summaries) < 2:
            return "stable"
        avgs = [s.avg_time for s in summaries]
        # Simple linear trend: compare first half avg to second half avg
        mid = len(avgs) // 2
        first_half = statistics.mean(avgs[:mid]) if mid > 0 else avgs[0]
        second_half = statistics.mean(avgs[mid:])
        if first_half == 0:
            return "stable"
        change = (second_half - first_half) / first_half
        if change > 0.1:
            return "degrading"
        if change < -0.1:
            return "improving"
        return "stable"

    @staticmethod
    def _percentile(sorted_values: list[float], pct: float) -> float:
        """Compute percentile from pre-sorted list."""
        if not sorted_values:
            return 0.0
        n = len(sorted_values)
        idx = (pct / 100) * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])
