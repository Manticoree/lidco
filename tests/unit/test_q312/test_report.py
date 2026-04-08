"""Tests for Q312 Task 1674 — PerformanceReport."""

from __future__ import annotations

import unittest

from lidco.loadtest.report import (
    BaselineComparison,
    ErrorBreakdown,
    LatencyPercentiles,
    PerformanceReport,
    ReportGenerator,
    ThroughputStats,
)
from lidco.loadtest.runner import LiveStats, RequestResult, RequestStatus, RunResult


def _make_result(latency: float, status: RequestStatus = RequestStatus.SUCCESS, code: int = 200, url: str = "http://x") -> RequestResult:
    return RequestResult(
        request_id="r",
        url=url,
        method="GET",
        status=status,
        status_code=code,
        latency_ms=latency,
        bytes_received=500 if status == RequestStatus.SUCCESS else 0,
    )


def _make_run(latencies: list[float], errors: int = 0, timeouts: int = 0) -> RunResult:
    results = []
    for i, lat in enumerate(latencies):
        if i < errors:
            results.append(_make_result(lat, RequestStatus.ERROR, 500))
        elif i < errors + timeouts:
            results.append(_make_result(lat, RequestStatus.TIMEOUT))
        else:
            results.append(_make_result(lat))

    stats = LiveStats(elapsed_seconds=1.0)
    for r in results:
        stats.record(r)

    return RunResult(profile_name="test", results=results, stats=stats)


class TestLatencyPercentiles(unittest.TestCase):
    def test_defaults(self):
        lp = LatencyPercentiles()
        self.assertEqual(lp.p50, 0.0)


class TestReportGenerator(unittest.TestCase):
    def test_empty_results(self):
        gen = ReportGenerator()
        run = RunResult(profile_name="empty", stats=LiveStats())
        report = gen.generate(run)
        self.assertEqual(report.profile_name, "empty")
        self.assertEqual(report.latency.p50, 0.0)
        self.assertEqual(report.throughput.total_requests, 0)
        self.assertTrue(report.passed)

    def test_basic_report(self):
        run = _make_run([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        gen = ReportGenerator()
        report = gen.generate(run)
        self.assertEqual(report.throughput.total_requests, 10)
        self.assertGreater(report.latency.p50, 0)
        self.assertGreater(report.latency.p95, 0)
        self.assertGreaterEqual(report.latency.p99, report.latency.p95)
        self.assertEqual(report.errors.total_errors, 0)
        self.assertTrue(report.passed)

    def test_latency_ordering(self):
        run = _make_run(list(range(1, 101)))
        gen = ReportGenerator()
        report = gen.generate(run)
        self.assertLessEqual(report.latency.p50, report.latency.p75)
        self.assertLessEqual(report.latency.p75, report.latency.p90)
        self.assertLessEqual(report.latency.p90, report.latency.p95)
        self.assertLessEqual(report.latency.p95, report.latency.p99)

    def test_error_breakdown(self):
        run = _make_run([10, 20, 30, 40, 50], errors=2)
        gen = ReportGenerator()
        report = gen.generate(run)
        self.assertEqual(report.errors.total_errors, 2)
        self.assertAlmostEqual(report.errors.error_rate, 0.4)
        self.assertIn(500, report.errors.errors_by_code)

    def test_timeout_breakdown(self):
        run = _make_run([10, 20, 30], errors=0, timeouts=1)
        gen = ReportGenerator()
        report = gen.generate(run)
        self.assertEqual(report.errors.total_timeouts, 1)

    def test_latency_threshold_fail(self):
        run = _make_run([500, 600, 700, 800, 900])
        gen = ReportGenerator(latency_threshold_ms=100.0)
        report = gen.generate(run)
        self.assertFalse(report.passed)

    def test_error_threshold_fail(self):
        run = _make_run([10, 20, 30], errors=3)
        gen = ReportGenerator(error_rate_threshold=0.5)
        report = gen.generate(run)
        self.assertFalse(report.passed)

    def test_to_text(self):
        run = _make_run([10, 20, 30])
        gen = ReportGenerator()
        report = gen.generate(run)
        text = report.to_text()
        self.assertIn("Load Test Report", text)
        self.assertIn("Latency", text)
        self.assertIn("Throughput", text)
        self.assertIn("Errors", text)

    def test_baseline_comparison_no_regression(self):
        base_run = _make_run([10, 20, 30, 40, 50])
        cur_run = _make_run([11, 21, 31, 41, 51])
        gen = ReportGenerator()
        report = gen.generate(cur_run, baseline=base_run)
        self.assertIsNotNone(report.baseline_comparison)
        self.assertFalse(report.baseline_comparison.regression)

    def test_baseline_comparison_with_regression(self):
        base_run = _make_run([10, 20, 30, 40, 50])
        cur_run = _make_run([100, 200, 300, 400, 500])
        gen = ReportGenerator()
        report = gen.generate(cur_run, baseline=base_run)
        self.assertIsNotNone(report.baseline_comparison)
        self.assertTrue(report.baseline_comparison.regression)
        self.assertGreater(report.baseline_comparison.latency_delta_pct, 0)

    def test_throughput_stats(self):
        run = _make_run([10] * 50)
        gen = ReportGenerator()
        report = gen.generate(run)
        self.assertEqual(report.throughput.total_requests, 50)
        self.assertGreater(report.throughput.requests_per_second, 0)
        self.assertGreater(report.throughput.bytes_per_second, 0)

    def test_summary_lines_include_baseline(self):
        base_run = _make_run([10, 20])
        cur_run = _make_run([100, 200])
        gen = ReportGenerator()
        report = gen.generate(cur_run, baseline=base_run)
        text = report.to_text()
        self.assertIn("Baseline", text)


class TestPerformanceReport(unittest.TestCase):
    def test_passed_default(self):
        r = PerformanceReport(profile_name="x")
        self.assertTrue(r.passed)

    def test_to_text_empty(self):
        r = PerformanceReport(profile_name="x", summary_lines=["line1", "line2"])
        self.assertEqual(r.to_text(), "line1\nline2")


if __name__ == "__main__":
    unittest.main()
