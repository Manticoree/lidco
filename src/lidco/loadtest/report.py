"""
Q312 Task 1674 — Performance Report

Latency percentiles, throughput, error rates, resource utilization,
comparison with baseline.  Stdlib only.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any

from lidco.loadtest.runner import LiveStats, RequestResult, RequestStatus, RunResult


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LatencyPercentiles:
    """Latency percentile breakdown."""

    p50: float = 0.0
    p75: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    stdev_ms: float = 0.0


@dataclass
class ThroughputStats:
    """Throughput statistics."""

    requests_per_second: float = 0.0
    bytes_per_second: float = 0.0
    total_requests: int = 0
    total_bytes: int = 0
    elapsed_seconds: float = 0.0


@dataclass
class ErrorBreakdown:
    """Error rate breakdown."""

    total_errors: int = 0
    total_timeouts: int = 0
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    errors_by_code: dict[int, int] = field(default_factory=dict)


@dataclass
class BaselineComparison:
    """Comparison between current run and a baseline."""

    latency_delta_pct: float = 0.0  # positive = slower
    throughput_delta_pct: float = 0.0  # positive = better
    error_rate_delta: float = 0.0  # positive = worse
    regression: bool = False
    summary: str = ""


@dataclass
class PerformanceReport:
    """Complete performance report after a load test run."""

    profile_name: str
    latency: LatencyPercentiles = field(default_factory=LatencyPercentiles)
    throughput: ThroughputStats = field(default_factory=ThroughputStats)
    errors: ErrorBreakdown = field(default_factory=ErrorBreakdown)
    baseline_comparison: BaselineComparison | None = None
    passed: bool = True
    summary_lines: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        return "\n".join(self.summary_lines)


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------


class ReportGenerator:
    """Build a PerformanceReport from a RunResult."""

    def __init__(
        self,
        latency_threshold_ms: float = 0.0,
        error_rate_threshold: float = 1.0,
    ) -> None:
        self.latency_threshold_ms = latency_threshold_ms
        self.error_rate_threshold = error_rate_threshold

    def generate(
        self,
        run: RunResult,
        baseline: RunResult | None = None,
    ) -> PerformanceReport:
        latencies = [r.latency_ms for r in run.results]
        latency = self._compute_latency(latencies)
        throughput = self._compute_throughput(run)
        errors = self._compute_errors(run)

        comparison: BaselineComparison | None = None
        if baseline is not None:
            comparison = self._compare_baseline(run, baseline)

        passed = True
        if self.latency_threshold_ms > 0 and latency.p95 > self.latency_threshold_ms:
            passed = False
        if errors.error_rate > self.error_rate_threshold:
            passed = False

        lines = self._build_summary(run, latency, throughput, errors, comparison, passed)

        return PerformanceReport(
            profile_name=run.profile_name,
            latency=latency,
            throughput=throughput,
            errors=errors,
            baseline_comparison=comparison,
            passed=passed,
            summary_lines=lines,
        )

    # ------------------------------------------------------------------
    # Latency
    # ------------------------------------------------------------------

    def _compute_latency(self, latencies: list[float]) -> LatencyPercentiles:
        if not latencies:
            return LatencyPercentiles()

        s = sorted(latencies)
        n = len(s)
        mean = statistics.mean(s)
        stdev = statistics.stdev(s) if n > 1 else 0.0

        return LatencyPercentiles(
            p50=self._percentile(s, 50),
            p75=self._percentile(s, 75),
            p90=self._percentile(s, 90),
            p95=self._percentile(s, 95),
            p99=self._percentile(s, 99),
            min_ms=s[0],
            max_ms=s[-1],
            mean_ms=round(mean, 3),
            stdev_ms=round(stdev, 3),
        )

    @staticmethod
    def _percentile(sorted_data: list[float], pct: float) -> float:
        if not sorted_data:
            return 0.0
        k = (pct / 100.0) * (len(sorted_data) - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return round(sorted_data[int(k)], 3)
        d0 = sorted_data[f] * (c - k)
        d1 = sorted_data[c] * (k - f)
        return round(d0 + d1, 3)

    # ------------------------------------------------------------------
    # Throughput
    # ------------------------------------------------------------------

    def _compute_throughput(self, run: RunResult) -> ThroughputStats:
        elapsed = run.stats.elapsed_seconds or 1.0
        total_bytes = sum(r.bytes_received for r in run.results)
        return ThroughputStats(
            requests_per_second=round(len(run.results) / elapsed, 2),
            bytes_per_second=round(total_bytes / elapsed, 2),
            total_requests=len(run.results),
            total_bytes=total_bytes,
            elapsed_seconds=round(elapsed, 3),
        )

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------

    def _compute_errors(self, run: RunResult) -> ErrorBreakdown:
        total = len(run.results)
        if total == 0:
            return ErrorBreakdown()

        errors = [r for r in run.results if r.status == RequestStatus.ERROR]
        timeouts = [r for r in run.results if r.status == RequestStatus.TIMEOUT]

        by_code: dict[int, int] = {}
        for r in errors:
            if r.status_code:
                by_code[r.status_code] = by_code.get(r.status_code, 0) + 1

        return ErrorBreakdown(
            total_errors=len(errors),
            total_timeouts=len(timeouts),
            error_rate=round((len(errors) + len(timeouts)) / total, 4),
            timeout_rate=round(len(timeouts) / total, 4),
            errors_by_code=by_code,
        )

    # ------------------------------------------------------------------
    # Baseline comparison
    # ------------------------------------------------------------------

    def _compare_baseline(self, run: RunResult, baseline: RunResult) -> BaselineComparison:
        cur_lat = [r.latency_ms for r in run.results]
        base_lat = [r.latency_ms for r in baseline.results]

        cur_p95 = self._percentile(sorted(cur_lat), 95) if cur_lat else 0.0
        base_p95 = self._percentile(sorted(base_lat), 95) if base_lat else 0.0

        lat_delta = 0.0
        if base_p95 > 0:
            lat_delta = round(((cur_p95 - base_p95) / base_p95) * 100, 2)

        cur_rps = len(run.results) / max(run.stats.elapsed_seconds, 1.0)
        base_rps = len(baseline.results) / max(baseline.stats.elapsed_seconds, 1.0)
        tp_delta = 0.0
        if base_rps > 0:
            tp_delta = round(((cur_rps - base_rps) / base_rps) * 100, 2)

        cur_err = run.stats.error_rate
        base_err = baseline.stats.error_rate
        err_delta = round(cur_err - base_err, 4)

        regression = lat_delta > 10 or err_delta > 0.05

        parts = []
        if lat_delta > 0:
            parts.append(f"latency +{lat_delta}%")
        elif lat_delta < 0:
            parts.append(f"latency {lat_delta}%")
        if tp_delta != 0:
            parts.append(f"throughput {tp_delta:+.1f}%")
        if regression:
            parts.append("REGRESSION")

        return BaselineComparison(
            latency_delta_pct=lat_delta,
            throughput_delta_pct=tp_delta,
            error_rate_delta=err_delta,
            regression=regression,
            summary="; ".join(parts) if parts else "No significant change",
        )

    # ------------------------------------------------------------------
    # Summary text
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        run: RunResult,
        latency: LatencyPercentiles,
        throughput: ThroughputStats,
        errors: ErrorBreakdown,
        comparison: BaselineComparison | None,
        passed: bool,
    ) -> list[str]:
        lines = [
            f"Load Test Report: {run.profile_name}",
            f"  Status: {'PASS' if passed else 'FAIL'}",
            "",
            "Latency:",
            f"  p50={latency.p50}ms  p90={latency.p90}ms  p95={latency.p95}ms  p99={latency.p99}ms",
            f"  min={latency.min_ms}ms  max={latency.max_ms}ms  mean={latency.mean_ms}ms  stdev={latency.stdev_ms}ms",
            "",
            "Throughput:",
            f"  {throughput.requests_per_second} req/s  |  {throughput.bytes_per_second} B/s",
            f"  Total: {throughput.total_requests} requests in {throughput.elapsed_seconds}s",
            "",
            "Errors:",
            f"  {errors.total_errors} errors, {errors.total_timeouts} timeouts ({errors.error_rate:.2%} error rate)",
        ]
        if errors.errors_by_code:
            for code, count in sorted(errors.errors_by_code.items()):
                lines.append(f"    HTTP {code}: {count}")

        if comparison:
            lines.append("")
            lines.append(f"Baseline: {comparison.summary}")

        return lines
