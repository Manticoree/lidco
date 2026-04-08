"""Tests for lidco.flaky.detector — FlakyDetector."""

from __future__ import annotations

import unittest

from lidco.flaky.detector import (
    DetectionReport,
    FlakyDetector,
    FlakyTestResult,
    FlakySeverity,
    TestRun,
)


class TestTestRun(unittest.TestCase):
    def test_defaults(self) -> None:
        r = TestRun(test_name="t1", passed=True)
        self.assertEqual(r.test_name, "t1")
        self.assertTrue(r.passed)
        self.assertEqual(r.duration_ms, 0.0)
        self.assertEqual(r.environment, "default")
        self.assertEqual(r.timestamp, "")

    def test_frozen(self) -> None:
        r = TestRun(test_name="t1", passed=True)
        with self.assertRaises(AttributeError):
            r.test_name = "changed"  # type: ignore[misc]


class TestFlakySeverity(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(FlakySeverity.LOW.value, "low")
        self.assertEqual(FlakySeverity.CRITICAL.value, "critical")


class TestFlakyDetector(unittest.TestCase):
    def _make_runs(
        self,
        name: str,
        passes: int,
        fails: int,
        *,
        env: str = "default",
        duration_ms: float = 100.0,
    ) -> list[TestRun]:
        runs: list[TestRun] = []
        for _ in range(passes):
            runs.append(TestRun(test_name=name, passed=True, duration_ms=duration_ms, environment=env))
        for _ in range(fails):
            runs.append(TestRun(test_name=name, passed=False, duration_ms=duration_ms, environment=env))
        return runs

    def test_empty_runs(self) -> None:
        d = FlakyDetector()
        report = d.detect([])
        self.assertEqual(report.total_tests, 0)
        self.assertEqual(report.flaky_count, 0)
        self.assertEqual(report.flaky_rate, 0.0)

    def test_all_passing(self) -> None:
        runs = self._make_runs("test_ok", 10, 0)
        report = FlakyDetector().detect(runs)
        self.assertEqual(report.total_tests, 1)
        self.assertEqual(report.flaky_count, 0)
        self.assertFalse(report.results[0].is_flaky)

    def test_all_failing(self) -> None:
        runs = self._make_runs("test_fail", 0, 10)
        report = FlakyDetector().detect(runs)
        self.assertEqual(report.total_tests, 1)
        # pass_rate=0.0, not > 0, so not flaky by pass/fail check alone
        # but 0 < 0.0 is False so not marked flaky unless env-sensitive
        r = report.results[0]
        self.assertEqual(r.fail_count, 10)

    def test_flaky_mixed(self) -> None:
        runs = self._make_runs("test_flaky", 5, 5)
        report = FlakyDetector(min_runs=3).detect(runs)
        self.assertEqual(report.flaky_count, 1)
        r = report.results[0]
        self.assertTrue(r.is_flaky)
        self.assertEqual(r.pass_rate, 0.5)

    def test_flaky_threshold(self) -> None:
        runs = self._make_runs("test_almost", 9, 1)
        # pass_rate = 0.9, below default 0.95 threshold
        report = FlakyDetector(min_runs=3).detect(runs)
        self.assertEqual(report.flaky_count, 1)
        self.assertTrue(report.results[0].is_flaky)

    def test_not_flaky_above_threshold(self) -> None:
        runs = self._make_runs("test_stable", 19, 1)
        # pass_rate = 0.95 — not below threshold
        report = FlakyDetector(min_runs=3, flaky_threshold=0.95).detect(runs)
        self.assertEqual(report.flaky_count, 0)

    def test_min_runs_filter(self) -> None:
        runs = self._make_runs("test_few", 1, 1)
        report = FlakyDetector(min_runs=5).detect(runs)
        self.assertFalse(report.results[0].is_flaky)

    def test_timing_variance_detection(self) -> None:
        runs = [
            TestRun(test_name="t", passed=True, duration_ms=100.0),
            TestRun(test_name="t", passed=True, duration_ms=200.0),
            TestRun(test_name="t", passed=True, duration_ms=1000.0),
            TestRun(test_name="t", passed=False, duration_ms=50.0),
        ]
        report = FlakyDetector(min_runs=3, timing_cv_threshold=0.3).detect(runs)
        r = report.results[0]
        self.assertTrue(r.timing_variance > 0)

    def test_environment_sensitivity(self) -> None:
        runs = []
        # All pass on linux, all fail on windows
        for _ in range(5):
            runs.append(TestRun(test_name="t", passed=True, environment="linux"))
        for _ in range(5):
            runs.append(TestRun(test_name="t", passed=False, environment="windows"))
        report = FlakyDetector(min_runs=3).detect(runs)
        r = report.results[0]
        self.assertTrue(r.is_flaky)
        self.assertTrue(r.environment_sensitive)

    def test_no_env_sensitivity_single_env(self) -> None:
        runs = self._make_runs("t", 5, 5, env="ci")
        report = FlakyDetector(min_runs=3).detect(runs)
        r = report.results[0]
        self.assertFalse(r.environment_sensitive)

    def test_severity_critical(self) -> None:
        runs = self._make_runs("t", 1, 9)  # pass_rate ~0.1
        report = FlakyDetector(min_runs=3).detect(runs)
        r = report.results[0]
        self.assertTrue(r.is_flaky)
        self.assertEqual(r.severity, FlakySeverity.CRITICAL)

    def test_severity_high(self) -> None:
        runs = self._make_runs("t", 4, 6)  # pass_rate=0.4
        report = FlakyDetector(min_runs=3).detect(runs)
        r = report.results[0]
        self.assertEqual(r.severity, FlakySeverity.HIGH)

    def test_severity_medium(self) -> None:
        runs = self._make_runs("t", 7, 3)  # pass_rate=0.7
        report = FlakyDetector(min_runs=3).detect(runs)
        r = report.results[0]
        self.assertEqual(r.severity, FlakySeverity.MEDIUM)

    def test_severity_low_not_flaky(self) -> None:
        runs = self._make_runs("t", 20, 0)
        report = FlakyDetector(min_runs=3).detect(runs)
        self.assertEqual(report.results[0].severity, FlakySeverity.LOW)

    def test_multiple_tests(self) -> None:
        runs = (
            self._make_runs("a", 10, 0)
            + self._make_runs("b", 5, 5)
            + self._make_runs("c", 3, 7)
        )
        report = FlakyDetector(min_runs=3).detect(runs)
        self.assertEqual(report.total_tests, 3)
        self.assertEqual(report.flaky_count, 2)
        names = {r.test_name for r in report.results if r.is_flaky}
        self.assertEqual(names, {"b", "c"})

    def test_detection_report_flaky_rate(self) -> None:
        runs = self._make_runs("a", 10, 0) + self._make_runs("b", 5, 5)
        report = FlakyDetector(min_runs=3).detect(runs)
        self.assertAlmostEqual(report.flaky_rate, 0.5)

    def test_flaky_test_result_environments_sorted(self) -> None:
        runs = [
            TestRun(test_name="t", passed=True, environment="z"),
            TestRun(test_name="t", passed=True, environment="a"),
            TestRun(test_name="t", passed=True, environment="m"),
        ]
        report = FlakyDetector(min_runs=1).detect(runs)
        self.assertEqual(report.results[0].environments, ["a", "m", "z"])

    def test_min_runs_at_least_one(self) -> None:
        d = FlakyDetector(min_runs=0)
        self.assertEqual(d._min_runs, 1)


class TestDetectionReport(unittest.TestCase):
    def test_defaults(self) -> None:
        r = DetectionReport(total_tests=0, flaky_count=0)
        self.assertEqual(r.results, [])
        self.assertEqual(r.flaky_rate, 0.0)


class TestFlakyTestResult(unittest.TestCase):
    def test_defaults(self) -> None:
        r = FlakyTestResult(
            test_name="t",
            total_runs=1,
            pass_count=1,
            fail_count=0,
            pass_rate=1.0,
            timing_variance=0.0,
        )
        self.assertEqual(r.environments, [])
        self.assertFalse(r.is_flaky)
        self.assertEqual(r.severity, FlakySeverity.LOW)


if __name__ == "__main__":
    unittest.main()
