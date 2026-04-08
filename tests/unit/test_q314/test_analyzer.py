"""Tests for lidco.flaky.analyzer — FlakyAnalyzer."""

from __future__ import annotations

import unittest

from lidco.flaky.analyzer import (
    AnalysisReport,
    AnalysisResult,
    CauseDetail,
    FlakyAnalyzer,
    RootCause,
)
from lidco.flaky.detector import TestRun


class TestRootCause(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(RootCause.TIMING.value, "timing")
        self.assertEqual(RootCause.ORDER_DEPENDENCY.value, "order_dependency")
        self.assertEqual(RootCause.SHARED_STATE.value, "shared_state")
        self.assertEqual(RootCause.EXTERNAL_DEPENDENCY.value, "external_dependency")
        self.assertEqual(RootCause.UNKNOWN.value, "unknown")


class TestCauseDetail(unittest.TestCase):
    def test_frozen(self) -> None:
        c = CauseDetail(cause=RootCause.TIMING, confidence=0.8, evidence="hi")
        with self.assertRaises(AttributeError):
            c.confidence = 0.1  # type: ignore[misc]


class TestFlakyAnalyzer(unittest.TestCase):
    def test_empty_runs(self) -> None:
        a = FlakyAnalyzer()
        report = a.analyze([])
        self.assertEqual(report.total_analyzed, 0)
        self.assertEqual(report.results, [])

    def test_below_min_runs_skipped(self) -> None:
        runs = [
            TestRun(test_name="t", passed=True),
            TestRun(test_name="t", passed=False),
        ]
        report = FlakyAnalyzer(min_runs=5).analyze(runs)
        self.assertEqual(report.total_analyzed, 0)

    def test_timing_cause_detected(self) -> None:
        runs = [
            TestRun(test_name="t", passed=True, duration_ms=100.0),
            TestRun(test_name="t", passed=False, duration_ms=2000.0),
            TestRun(test_name="t", passed=True, duration_ms=50.0),
            TestRun(test_name="t", passed=True, duration_ms=3000.0),
        ]
        report = FlakyAnalyzer(min_runs=3, timing_threshold_ms=500.0).analyze(runs)
        self.assertEqual(report.total_analyzed, 1)
        result = report.results[0]
        causes = {c.cause for c in result.causes}
        self.assertIn(RootCause.TIMING, causes)

    def test_order_dependency_detected(self) -> None:
        # All failures in first half, none in second
        runs = [
            TestRun(test_name="t", passed=False),
            TestRun(test_name="t", passed=False),
            TestRun(test_name="t", passed=False),
            TestRun(test_name="t", passed=True),
            TestRun(test_name="t", passed=True),
            TestRun(test_name="t", passed=True),
        ]
        report = FlakyAnalyzer(min_runs=3).analyze(runs)
        result = report.results[0]
        causes = {c.cause for c in result.causes}
        self.assertIn(RootCause.ORDER_DEPENDENCY, causes)

    def test_shared_state_detected(self) -> None:
        # 3+ consecutive failures
        runs = [
            TestRun(test_name="t", passed=True),
            TestRun(test_name="t", passed=False),
            TestRun(test_name="t", passed=False),
            TestRun(test_name="t", passed=False),
            TestRun(test_name="t", passed=True),
        ]
        report = FlakyAnalyzer(min_runs=3).analyze(runs)
        result = report.results[0]
        causes = {c.cause for c in result.causes}
        self.assertIn(RootCause.SHARED_STATE, causes)

    def test_external_dependency_detected(self) -> None:
        runs = [
            TestRun(test_name="t", passed=True, environment="linux"),
            TestRun(test_name="t", passed=True, environment="linux"),
            TestRun(test_name="t", passed=True, environment="linux"),
            TestRun(test_name="t", passed=False, environment="mac"),
            TestRun(test_name="t", passed=False, environment="mac"),
            TestRun(test_name="t", passed=False, environment="mac"),
        ]
        report = FlakyAnalyzer(min_runs=3).analyze(runs)
        result = report.results[0]
        causes = {c.cause for c in result.causes}
        self.assertIn(RootCause.EXTERNAL_DEPENDENCY, causes)

    def test_unknown_cause_fallback(self) -> None:
        runs = [
            TestRun(test_name="t", passed=True, duration_ms=100.0),
            TestRun(test_name="t", passed=True, duration_ms=100.0),
            TestRun(test_name="t", passed=True, duration_ms=100.0),
        ]
        report = FlakyAnalyzer(min_runs=3).analyze(runs)
        result = report.results[0]
        self.assertEqual(result.primary_cause, RootCause.UNKNOWN)

    def test_recommendation_present(self) -> None:
        runs = [
            TestRun(test_name="t", passed=True, duration_ms=100.0),
            TestRun(test_name="t", passed=False, duration_ms=5000.0),
            TestRun(test_name="t", passed=True, duration_ms=50.0),
        ]
        report = FlakyAnalyzer(min_runs=3, timing_threshold_ms=100.0).analyze(runs)
        result = report.results[0]
        self.assertTrue(len(result.recommendation) > 0)

    def test_cause_counts(self) -> None:
        runs = [
            TestRun(test_name="a", passed=True, duration_ms=100.0),
            TestRun(test_name="a", passed=False, duration_ms=5000.0),
            TestRun(test_name="a", passed=True, duration_ms=50.0),
            TestRun(test_name="b", passed=True),
            TestRun(test_name="b", passed=True),
            TestRun(test_name="b", passed=True),
        ]
        report = FlakyAnalyzer(min_runs=3, timing_threshold_ms=100.0).analyze(runs)
        self.assertIn("unknown", report.cause_counts)

    def test_multiple_causes(self) -> None:
        # Timing + shared state + order dependency
        runs = [
            TestRun(test_name="t", passed=False, duration_ms=5000.0),
            TestRun(test_name="t", passed=False, duration_ms=5000.0),
            TestRun(test_name="t", passed=False, duration_ms=5000.0),
            TestRun(test_name="t", passed=True, duration_ms=50.0),
            TestRun(test_name="t", passed=True, duration_ms=50.0),
            TestRun(test_name="t", passed=True, duration_ms=50.0),
        ]
        report = FlakyAnalyzer(min_runs=3, timing_threshold_ms=100.0).analyze(runs)
        result = report.results[0]
        self.assertTrue(len(result.causes) >= 2)

    def test_primary_cause_highest_confidence(self) -> None:
        runs = [
            TestRun(test_name="t", passed=True, duration_ms=100.0),
            TestRun(test_name="t", passed=False, duration_ms=5000.0),
            TestRun(test_name="t", passed=True, duration_ms=50.0),
        ]
        report = FlakyAnalyzer(min_runs=3, timing_threshold_ms=100.0).analyze(runs)
        result = report.results[0]
        # Primary cause should be the one with highest confidence
        max_conf = max(c.confidence for c in result.causes)
        primary_conf = next(
            c.confidence for c in result.causes if c.cause == result.primary_cause
        )
        self.assertEqual(primary_conf, max_conf)

    def test_recommend_all_causes(self) -> None:
        for cause in RootCause:
            rec = FlakyAnalyzer._recommend(cause)
            self.assertTrue(len(rec) > 0)

    def test_min_runs_at_least_one(self) -> None:
        a = FlakyAnalyzer(min_runs=0)
        self.assertEqual(a._min_runs, 1)


class TestAnalysisReport(unittest.TestCase):
    def test_defaults(self) -> None:
        r = AnalysisReport(total_analyzed=0)
        self.assertEqual(r.results, [])
        self.assertEqual(r.cause_counts, {})


class TestAnalysisResult(unittest.TestCase):
    def test_defaults(self) -> None:
        r = AnalysisResult(test_name="t")
        self.assertEqual(r.causes, [])
        self.assertEqual(r.primary_cause, RootCause.UNKNOWN)
        self.assertEqual(r.recommendation, "")


if __name__ == "__main__":
    unittest.main()
