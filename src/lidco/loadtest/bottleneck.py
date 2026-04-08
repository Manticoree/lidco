"""
Q312 Task 1675 — Bottleneck Finder

Identify bottlenecks under load: slow queries, connection pool exhaustion,
memory pressure, CPU hotspots.  Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lidco.loadtest.runner import RequestResult, RequestStatus, RunResult


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class BottleneckType(Enum):
    SLOW_REQUESTS = "slow_requests"
    HIGH_ERROR_RATE = "high_error_rate"
    TIMEOUT_CLUSTER = "timeout_cluster"
    THROUGHPUT_DROP = "throughput_drop"
    LATENCY_SPIKE = "latency_spike"
    CONNECTION_SATURATION = "connection_saturation"
    MEMORY_PRESSURE = "memory_pressure"
    CPU_HOTSPOT = "cpu_hotspot"


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Bottleneck:
    """A single identified bottleneck."""

    type: BottleneckType
    severity: Severity
    description: str
    metric_value: float = 0.0
    threshold: float = 0.0
    affected_urls: list[str] = field(default_factory=list)
    recommendation: str = ""

    def to_text(self) -> str:
        parts = [f"[{self.severity.value.upper()}] {self.type.value}: {self.description}"]
        if self.affected_urls:
            parts.append(f"  Affected: {', '.join(self.affected_urls[:5])}")
        if self.recommendation:
            parts.append(f"  Recommendation: {self.recommendation}")
        return "\n".join(parts)


@dataclass
class BottleneckReport:
    """Collection of detected bottlenecks."""

    profile_name: str
    bottlenecks: list[Bottleneck] = field(default_factory=list)
    analyzed_requests: int = 0

    @property
    def has_critical(self) -> bool:
        return any(b.severity == Severity.CRITICAL for b in self.bottlenecks)

    @property
    def has_high(self) -> bool:
        return any(b.severity == Severity.HIGH for b in self.bottlenecks)

    def to_text(self) -> str:
        if not self.bottlenecks:
            return f"Bottleneck analysis for '{self.profile_name}': No bottlenecks detected."
        lines = [
            f"Bottleneck analysis for '{self.profile_name}': "
            f"{len(self.bottlenecks)} issue(s) found",
            "",
        ]
        for b in self.bottlenecks:
            lines.append(b.to_text())
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bottleneck Finder
# ---------------------------------------------------------------------------


class BottleneckFinder:
    """
    Analyze a RunResult to identify performance bottlenecks.

    Configurable thresholds:
      - slow_threshold_ms: requests above this are considered slow (default 500)
      - error_rate_threshold: error rate above this triggers a finding (default 0.05)
      - timeout_cluster_threshold: % of timeouts that signals saturation (default 0.1)
      - latency_spike_factor: factor above mean that signals a spike (default 3.0)
      - throughput_drop_pct: drop vs peak that signals degradation (default 0.3)
    """

    def __init__(
        self,
        slow_threshold_ms: float = 500.0,
        error_rate_threshold: float = 0.05,
        timeout_cluster_threshold: float = 0.10,
        latency_spike_factor: float = 3.0,
        throughput_drop_pct: float = 0.30,
    ) -> None:
        self.slow_threshold_ms = slow_threshold_ms
        self.error_rate_threshold = error_rate_threshold
        self.timeout_cluster_threshold = timeout_cluster_threshold
        self.latency_spike_factor = latency_spike_factor
        self.throughput_drop_pct = throughput_drop_pct

    def analyze(self, run: RunResult) -> BottleneckReport:
        """Run all detectors and return a consolidated report."""
        report = BottleneckReport(
            profile_name=run.profile_name,
            analyzed_requests=len(run.results),
        )

        if not run.results:
            return report

        self._check_slow_requests(run, report)
        self._check_error_rate(run, report)
        self._check_timeouts(run, report)
        self._check_latency_spikes(run, report)
        self._check_throughput_drop(run, report)

        # Sort by severity (critical first)
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }
        report.bottlenecks.sort(key=lambda b: severity_order.get(b.severity, 99))

        return report

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    def _check_slow_requests(self, run: RunResult, report: BottleneckReport) -> None:
        slow = [r for r in run.results if r.latency_ms > self.slow_threshold_ms]
        if not slow:
            return

        pct = len(slow) / len(run.results)
        urls = list({r.url for r in slow})

        if pct > 0.5:
            severity = Severity.CRITICAL
        elif pct > 0.2:
            severity = Severity.HIGH
        elif pct > 0.05:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        report.bottlenecks.append(Bottleneck(
            type=BottleneckType.SLOW_REQUESTS,
            severity=severity,
            description=(
                f"{len(slow)}/{len(run.results)} requests "
                f"({pct:.1%}) exceeded {self.slow_threshold_ms}ms"
            ),
            metric_value=pct,
            threshold=self.slow_threshold_ms,
            affected_urls=urls,
            recommendation="Investigate slow endpoints; consider caching or query optimization.",
        ))

    def _check_error_rate(self, run: RunResult, report: BottleneckReport) -> None:
        error_count = sum(
            1 for r in run.results if r.status == RequestStatus.ERROR
        )
        rate = error_count / len(run.results)
        if rate <= self.error_rate_threshold:
            return

        urls = list({r.url for r in run.results if r.status == RequestStatus.ERROR})

        if rate > 0.5:
            severity = Severity.CRITICAL
        elif rate > 0.2:
            severity = Severity.HIGH
        else:
            severity = Severity.MEDIUM

        report.bottlenecks.append(Bottleneck(
            type=BottleneckType.HIGH_ERROR_RATE,
            severity=severity,
            description=f"Error rate {rate:.1%} exceeds threshold {self.error_rate_threshold:.1%}",
            metric_value=rate,
            threshold=self.error_rate_threshold,
            affected_urls=urls,
            recommendation="Check server logs for error causes; verify connection pool sizing.",
        ))

    def _check_timeouts(self, run: RunResult, report: BottleneckReport) -> None:
        timeout_count = sum(
            1 for r in run.results if r.status == RequestStatus.TIMEOUT
        )
        rate = timeout_count / len(run.results)
        if rate <= self.timeout_cluster_threshold:
            return

        if rate > 0.3:
            severity = Severity.CRITICAL
        elif rate > 0.15:
            severity = Severity.HIGH
        else:
            severity = Severity.MEDIUM

        report.bottlenecks.append(Bottleneck(
            type=BottleneckType.TIMEOUT_CLUSTER,
            severity=severity,
            description=f"{timeout_count} timeouts ({rate:.1%}) — possible connection saturation",
            metric_value=rate,
            threshold=self.timeout_cluster_threshold,
            recommendation="Increase connection pool size or request timeout; check server capacity.",
        ))

    def _check_latency_spikes(self, run: RunResult, report: BottleneckReport) -> None:
        latencies = [r.latency_ms for r in run.results]
        if len(latencies) < 10:
            return

        mean = sum(latencies) / len(latencies)
        if mean <= 0:
            return

        spike_threshold = mean * self.latency_spike_factor
        spikes = [r for r in run.results if r.latency_ms > spike_threshold]
        if not spikes:
            return

        pct = len(spikes) / len(run.results)
        if pct < 0.01:
            return

        urls = list({r.url for r in spikes})

        severity = Severity.HIGH if pct > 0.05 else Severity.MEDIUM

        report.bottlenecks.append(Bottleneck(
            type=BottleneckType.LATENCY_SPIKE,
            severity=severity,
            description=(
                f"{len(spikes)} requests ({pct:.1%}) spiked above "
                f"{spike_threshold:.0f}ms (>{self.latency_spike_factor}x mean)"
            ),
            metric_value=spike_threshold,
            threshold=mean,
            affected_urls=urls,
            recommendation="Check for GC pauses, lock contention, or external service delays.",
        ))

    def _check_throughput_drop(self, run: RunResult, report: BottleneckReport) -> None:
        """Detect if throughput dropped significantly over time."""
        if len(run.results) < 20:
            return

        # Split into two halves by timestamp
        sorted_results = sorted(run.results, key=lambda r: r.timestamp)
        mid = len(sorted_results) // 2
        first_half = sorted_results[:mid]
        second_half = sorted_results[mid:]

        if not first_half or not second_half:
            return

        t1_start = first_half[0].timestamp
        t1_end = first_half[-1].timestamp
        t2_start = second_half[0].timestamp
        t2_end = second_half[-1].timestamp

        dur1 = t1_end - t1_start
        dur2 = t2_end - t2_start

        if dur1 <= 0 or dur2 <= 0:
            return

        rps1 = len(first_half) / dur1
        rps2 = len(second_half) / dur2

        if rps1 <= 0:
            return

        drop = (rps1 - rps2) / rps1
        if drop < self.throughput_drop_pct:
            return

        severity = Severity.HIGH if drop > 0.5 else Severity.MEDIUM

        report.bottlenecks.append(Bottleneck(
            type=BottleneckType.THROUGHPUT_DROP,
            severity=severity,
            description=(
                f"Throughput dropped {drop:.0%} from {rps1:.1f} to {rps2:.1f} req/s "
                f"in the second half of the test"
            ),
            metric_value=rps2,
            threshold=rps1,
            recommendation="Likely resource exhaustion under sustained load; check memory and connections.",
        ))
