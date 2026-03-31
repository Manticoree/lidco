"""BottleneckDetector — find slow operations from timing records."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.perf.timing_profiler import TimingRecord


@dataclass
class Bottleneck:
    """A detected performance bottleneck."""

    name: str
    avg_time: float
    call_count: int
    total_time: float
    percentage: float
    severity: str  # "low" / "medium" / "high"


class BottleneckDetector:
    """Analyze timing records to detect bottlenecks."""

    def __init__(self, threshold_ms: float = 100.0) -> None:
        self._threshold_ms = threshold_ms

    def analyze(self, records: list[TimingRecord]) -> list[Bottleneck]:
        """Group records by name and find operations exceeding threshold."""
        if not records:
            return []

        groups: dict[str, list[float]] = {}
        for r in records:
            groups.setdefault(r.name, []).append(r.elapsed)

        grand_total = sum(r.elapsed for r in records)
        if grand_total == 0:
            grand_total = 1e-9

        result: list[Bottleneck] = []
        for name, times in groups.items():
            total = sum(times)
            avg = total / len(times)
            avg_ms = avg * 1000
            pct = (total / grand_total) * 100

            if avg_ms >= self._threshold_ms:
                severity = self._classify(avg_ms)
                result.append(Bottleneck(
                    name=name,
                    avg_time=avg,
                    call_count=len(times),
                    total_time=total,
                    percentage=pct,
                    severity=severity,
                ))

        return sorted(result, key=lambda b: b.total_time, reverse=True)

    def top_bottlenecks(self, records: list[TimingRecord], n: int = 5) -> list[Bottleneck]:
        """Return top *n* bottlenecks sorted by total_time."""
        # Analyze with threshold=0 to capture everything, then take top n
        old_thresh = self._threshold_ms
        self._threshold_ms = 0.0
        try:
            all_bottlenecks = self.analyze(records)
        finally:
            self._threshold_ms = old_thresh
        return all_bottlenecks[:n]

    def format_report(self, bottlenecks: list[Bottleneck]) -> str:
        """Format bottlenecks as a table-like report."""
        if not bottlenecks:
            return "No bottlenecks detected."
        lines = [
            "Bottleneck Report",
            "=" * 70,
            f"{'Name':30s} {'Avg(ms)':>10s} {'Count':>6s} {'Total(ms)':>10s} {'%':>6s} {'Sev':>6s}",
            "-" * 70,
        ]
        for b in bottlenecks:
            lines.append(
                f"{b.name:30s} {b.avg_time * 1000:10.2f} {b.call_count:6d} "
                f"{b.total_time * 1000:10.2f} {b.percentage:5.1f}% {b.severity:>6s}"
            )
        return "\n".join(lines)

    def suggest_optimizations(self, bottlenecks: list[Bottleneck]) -> list[str]:
        """Return generic optimization suggestions based on bottleneck patterns."""
        if not bottlenecks:
            return []
        suggestions: list[str] = []
        for b in bottlenecks:
            name_lower = b.name.lower()
            if b.severity == "high":
                suggestions.append(f"CRITICAL: '{b.name}' averages {b.avg_time * 1000:.0f}ms — consider caching or async execution.")
            if b.call_count > 10:
                suggestions.append(f"'{b.name}' called {b.call_count} times — consider batching or memoization.")
            if "io" in name_lower or "read" in name_lower or "write" in name_lower or "file" in name_lower:
                suggestions.append(f"'{b.name}' appears I/O-bound — consider buffering or async I/O.")
            if "db" in name_lower or "query" in name_lower or "sql" in name_lower:
                suggestions.append(f"'{b.name}' appears database-related — consider query optimization or connection pooling.")
            if b.percentage > 50:
                suggestions.append(f"'{b.name}' consumes {b.percentage:.0f}% of total time — primary optimization target.")
        if not suggestions:
            suggestions.append("Review high-severity bottlenecks for caching and concurrency opportunities.")
        return suggestions

    def _classify(self, avg_ms: float) -> str:
        """Classify severity based on average time in ms."""
        if avg_ms >= 1000:
            return "high"
        if avg_ms >= 500:
            return "medium"
        return "low"
