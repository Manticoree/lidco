"""Tests for Q312 Task 1675 — BottleneckFinder."""

from __future__ import annotations

import time
import unittest

from lidco.loadtest.bottleneck import (
    Bottleneck,
    BottleneckFinder,
    BottleneckReport,
    BottleneckType,
    Severity,
)
from lidco.loadtest.runner import LiveStats, RequestResult, RequestStatus, RunResult


def _result(
    latency: float,
    status: RequestStatus = RequestStatus.SUCCESS,
    url: str = "http://x",
    ts: float | None = None,
) -> RequestResult:
    return RequestResult(
        request_id="r",
        url=url,
        method="GET",
        status=status,
        status_code=200 if status == RequestStatus.SUCCESS else 500,
        latency_ms=latency,
        bytes_received=100,
        timestamp=ts if ts is not None else time.time(),
    )


def _run(results: list[RequestResult]) -> RunResult:
    stats = LiveStats(elapsed_seconds=1.0)
    for r in results:
        stats.record(r)
    return RunResult(profile_name="test", results=results, stats=stats)


class TestBottleneck(unittest.TestCase):
    def test_to_text(self):
        b = Bottleneck(
            type=BottleneckType.SLOW_REQUESTS,
            severity=Severity.HIGH,
            description="50% slow",
            affected_urls=["http://a"],
            recommendation="Fix it",
        )
        text = b.to_text()
        self.assertIn("HIGH", text)
        self.assertIn("slow_requests", text)
        self.assertIn("http://a", text)
        self.assertIn("Fix it", text)


class TestBottleneckReport(unittest.TestCase):
    def test_empty(self):
        r = BottleneckReport(profile_name="t")
        self.assertFalse(r.has_critical)
        self.assertFalse(r.has_high)
        self.assertIn("No bottlenecks", r.to_text())

    def test_has_critical(self):
        r = BottleneckReport(
            profile_name="t",
            bottlenecks=[Bottleneck(
                type=BottleneckType.HIGH_ERROR_RATE,
                severity=Severity.CRITICAL,
                description="x",
            )],
        )
        self.assertTrue(r.has_critical)

    def test_to_text_with_findings(self):
        r = BottleneckReport(
            profile_name="t",
            bottlenecks=[Bottleneck(
                type=BottleneckType.SLOW_REQUESTS,
                severity=Severity.MEDIUM,
                description="slow",
            )],
        )
        text = r.to_text()
        self.assertIn("1 issue(s)", text)


class TestBottleneckFinder(unittest.TestCase):
    def test_empty_results(self):
        finder = BottleneckFinder()
        run = RunResult(profile_name="empty", stats=LiveStats())
        report = finder.analyze(run)
        self.assertEqual(report.bottlenecks, [])
        self.assertEqual(report.analyzed_requests, 0)

    def test_no_bottlenecks(self):
        results = [_result(50) for _ in range(20)]
        finder = BottleneckFinder(slow_threshold_ms=500)
        report = finder.analyze(_run(results))
        # No slow, no errors, no timeouts, no spikes
        slow_findings = [b for b in report.bottlenecks if b.type == BottleneckType.SLOW_REQUESTS]
        self.assertEqual(len(slow_findings), 0)

    def test_detect_slow_requests(self):
        results = [_result(600) for _ in range(10)]
        finder = BottleneckFinder(slow_threshold_ms=500)
        report = finder.analyze(_run(results))
        slow = [b for b in report.bottlenecks if b.type == BottleneckType.SLOW_REQUESTS]
        self.assertEqual(len(slow), 1)
        self.assertEqual(slow[0].severity, Severity.CRITICAL)  # 100% > 50%

    def test_detect_slow_requests_medium(self):
        # 10% slow
        results = [_result(600)] + [_result(50) for _ in range(9)]
        finder = BottleneckFinder(slow_threshold_ms=500)
        report = finder.analyze(_run(results))
        slow = [b for b in report.bottlenecks if b.type == BottleneckType.SLOW_REQUESTS]
        self.assertEqual(len(slow), 1)
        self.assertEqual(slow[0].severity, Severity.MEDIUM)

    def test_detect_high_error_rate(self):
        results = [
            _result(50, RequestStatus.ERROR) for _ in range(6)
        ] + [_result(50) for _ in range(4)]
        finder = BottleneckFinder(error_rate_threshold=0.05)
        report = finder.analyze(_run(results))
        err = [b for b in report.bottlenecks if b.type == BottleneckType.HIGH_ERROR_RATE]
        self.assertEqual(len(err), 1)
        self.assertIn(err[0].severity, (Severity.HIGH, Severity.CRITICAL))

    def test_no_error_rate_below_threshold(self):
        results = [_result(50) for _ in range(100)]
        finder = BottleneckFinder(error_rate_threshold=0.05)
        report = finder.analyze(_run(results))
        err = [b for b in report.bottlenecks if b.type == BottleneckType.HIGH_ERROR_RATE]
        self.assertEqual(len(err), 0)

    def test_detect_timeout_cluster(self):
        results = [
            _result(30000, RequestStatus.TIMEOUT) for _ in range(5)
        ] + [_result(50) for _ in range(5)]
        finder = BottleneckFinder(timeout_cluster_threshold=0.1)
        report = finder.analyze(_run(results))
        to = [b for b in report.bottlenecks if b.type == BottleneckType.TIMEOUT_CLUSTER]
        self.assertEqual(len(to), 1)

    def test_detect_latency_spikes(self):
        # Mean ~50ms, spikes at 500ms
        results = [_result(50) for _ in range(90)] + [_result(500) for _ in range(10)]
        finder = BottleneckFinder(latency_spike_factor=3.0)
        report = finder.analyze(_run(results))
        spikes = [b for b in report.bottlenecks if b.type == BottleneckType.LATENCY_SPIKE]
        self.assertEqual(len(spikes), 1)

    def test_no_latency_spike_uniform(self):
        results = [_result(50) for _ in range(100)]
        finder = BottleneckFinder(latency_spike_factor=3.0)
        report = finder.analyze(_run(results))
        spikes = [b for b in report.bottlenecks if b.type == BottleneckType.LATENCY_SPIKE]
        self.assertEqual(len(spikes), 0)

    def test_detect_throughput_drop(self):
        now = time.time()
        # First half: fast (many requests per second)
        first = [_result(10, ts=now + i * 0.01) for i in range(50)]
        # Second half: slow (few requests per second)
        second = [_result(10, ts=now + 1.0 + i * 0.1) for i in range(50)]
        results = first + second
        finder = BottleneckFinder(throughput_drop_pct=0.3)
        report = finder.analyze(_run(results))
        drops = [b for b in report.bottlenecks if b.type == BottleneckType.THROUGHPUT_DROP]
        self.assertEqual(len(drops), 1)

    def test_sort_by_severity(self):
        results = [
            _result(600, RequestStatus.ERROR) for _ in range(10)
        ]
        finder = BottleneckFinder(
            slow_threshold_ms=500,
            error_rate_threshold=0.05,
        )
        report = finder.analyze(_run(results))
        if len(report.bottlenecks) >= 2:
            severities = [b.severity for b in report.bottlenecks]
            severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
            orders = [severity_order[s] for s in severities]
            self.assertEqual(orders, sorted(orders))

    def test_affected_urls(self):
        results = [_result(600, url="http://slow")] + [_result(50, url="http://fast") for _ in range(9)]
        finder = BottleneckFinder(slow_threshold_ms=500)
        report = finder.analyze(_run(results))
        slow = [b for b in report.bottlenecks if b.type == BottleneckType.SLOW_REQUESTS]
        if slow:
            self.assertIn("http://slow", slow[0].affected_urls)


if __name__ == "__main__":
    unittest.main()
