"""Tests for lidco.apitest.report — task 1695."""

from __future__ import annotations

import json
import unittest

from lidco.apitest.builder import Assertion
from lidco.apitest.report import (
    ApiTestReporter,
    Baseline,
    BaselineEntry,
    CaseReport,
    SuiteReport,
)
from lidco.apitest.runner import AssertionResult, SuiteResult, TestCaseResult


class TestBaselineEntry(unittest.TestCase):
    """Test BaselineEntry frozen dataclass."""

    def test_defaults(self) -> None:
        e = BaselineEntry(name="test", avg_duration_ms=100.0)
        self.assertEqual(e.expected_status, 200)

    def test_custom(self) -> None:
        e = BaselineEntry(name="t", avg_duration_ms=50.0, expected_status=201)
        self.assertEqual(e.expected_status, 201)


class TestBaseline(unittest.TestCase):
    """Test Baseline lookup."""

    def test_get_existing(self) -> None:
        bl = Baseline(entries={"t1": BaselineEntry(name="t1", avg_duration_ms=100.0)})
        self.assertIsNotNone(bl.get("t1"))
        self.assertIsNone(bl.get("missing"))


class TestApiTestReporter(unittest.TestCase):
    """Test ApiTestReporter.build_report."""

    def _make_result(
        self,
        name: str = "suite",
        cases: tuple[TestCaseResult, ...] | None = None,
    ) -> SuiteResult:
        if cases is None:
            cases = (
                TestCaseResult(
                    name="c1",
                    passed=True,
                    status_code=200,
                    duration_ms=50.0,
                ),
                TestCaseResult(
                    name="c2",
                    passed=False,
                    status_code=500,
                    duration_ms=150.0,
                    error="server error",
                    assertion_results=(
                        AssertionResult(
                            assertion=Assertion(field="status", operator="eq", expected=200),
                            passed=False,
                            actual=500,
                        ),
                    ),
                ),
            )
        total = len(cases)
        passed = sum(1 for c in cases if c.passed)
        return SuiteResult(
            name=name,
            passed=passed == total,
            total=total,
            passed_count=passed,
            failed_count=total - passed,
            results=cases,
            duration_ms=200.0,
        )

    def test_build_report_basic(self) -> None:
        reporter = ApiTestReporter()
        result = self._make_result()
        report = reporter.build_report(result)

        self.assertEqual(report.name, "suite")
        self.assertFalse(report.passed)
        self.assertEqual(report.total, 2)
        self.assertEqual(report.passed_count, 1)
        self.assertEqual(report.failed_count, 1)
        self.assertEqual(len(report.cases), 2)

    def test_duration_stats(self) -> None:
        reporter = ApiTestReporter()
        result = self._make_result()
        report = reporter.build_report(result)

        self.assertEqual(report.min_duration_ms, 50.0)
        self.assertEqual(report.max_duration_ms, 150.0)
        self.assertEqual(report.avg_duration_ms, 100.0)

    def test_assertion_failures_collected(self) -> None:
        reporter = ApiTestReporter()
        result = self._make_result()
        report = reporter.build_report(result)

        c2 = report.cases[1]
        self.assertEqual(len(c2.assertion_failures), 1)
        self.assertIn("status", c2.assertion_failures[0])
        self.assertIn("500", c2.assertion_failures[0])

    def test_baseline_comparison(self) -> None:
        baseline = Baseline(entries={
            "c1": BaselineEntry(name="c1", avg_duration_ms=40.0, expected_status=200),
            "c2": BaselineEntry(name="c2", avg_duration_ms=100.0, expected_status=200),
        })
        reporter = ApiTestReporter(baseline=baseline)
        result = self._make_result()
        report = reporter.build_report(result)

        # c1: 50ms vs 40ms baseline = +10ms diff, status matches
        self.assertEqual(report.cases[0].baseline_diff_ms, 10.0)
        self.assertTrue(report.cases[0].baseline_status_match)

        # c2: 150ms vs 100ms baseline = +50ms diff, status mismatch
        self.assertEqual(report.cases[1].baseline_diff_ms, 50.0)
        self.assertFalse(report.cases[1].baseline_status_match)

    def test_no_baseline(self) -> None:
        reporter = ApiTestReporter()
        result = self._make_result()
        report = reporter.build_report(result)

        self.assertIsNone(report.cases[0].baseline_diff_ms)
        self.assertIsNone(report.cases[0].baseline_status_match)


class TestFormatText(unittest.TestCase):
    """Test ApiTestReporter.format_text."""

    def test_text_output(self) -> None:
        cases = (
            TestCaseResult(name="ok", passed=True, status_code=200, duration_ms=10.0),
            TestCaseResult(name="fail", passed=False, status_code=500, duration_ms=20.0, error="boom"),
        )
        result = SuiteResult(
            name="s", passed=False, total=2, passed_count=1, failed_count=1,
            results=cases, duration_ms=30.0,
        )
        reporter = ApiTestReporter()
        report = reporter.build_report(result)
        text = reporter.format_text(report)

        self.assertIn("API Test Report: s", text)
        self.assertIn("FAIL", text)
        self.assertIn("[PASS] ok", text)
        self.assertIn("[FAIL] fail", text)
        self.assertIn("Error: boom", text)

    def test_text_baseline_info(self) -> None:
        cases = (
            TestCaseResult(name="t", passed=True, status_code=200, duration_ms=100.0),
        )
        result = SuiteResult(
            name="bl", passed=True, total=1, passed_count=1, failed_count=0,
            results=cases, duration_ms=100.0,
        )
        baseline = Baseline(entries={
            "t": BaselineEntry(name="t", avg_duration_ms=80.0, expected_status=200),
        })
        reporter = ApiTestReporter(baseline=baseline)
        report = reporter.build_report(result)
        text = reporter.format_text(report)

        self.assertIn("Baseline diff: +20.0ms", text)


class TestFormatJson(unittest.TestCase):
    """Test ApiTestReporter.format_json."""

    def test_json_output(self) -> None:
        cases = (
            TestCaseResult(name="j", passed=True, status_code=200, duration_ms=5.0),
        )
        result = SuiteResult(
            name="json-suite", passed=True, total=1, passed_count=1, failed_count=0,
            results=cases, duration_ms=5.0,
        )
        reporter = ApiTestReporter()
        report = reporter.build_report(result)
        text = reporter.format_json(report)
        data = json.loads(text)

        self.assertEqual(data["name"], "json-suite")
        self.assertTrue(data["passed"])
        self.assertEqual(len(data["cases"]), 1)
        self.assertEqual(data["cases"][0]["name"], "j")

    def test_empty_suite(self) -> None:
        result = SuiteResult(
            name="empty", passed=True, total=0, passed_count=0, failed_count=0,
            results=(), duration_ms=0.0,
        )
        reporter = ApiTestReporter()
        report = reporter.build_report(result)

        self.assertEqual(report.avg_duration_ms, 0.0)
        self.assertEqual(report.min_duration_ms, 0.0)
        self.assertEqual(report.max_duration_ms, 0.0)


class TestCaseReportDataclass(unittest.TestCase):
    """Test CaseReport and SuiteReport frozen dataclasses."""

    def test_case_report_frozen(self) -> None:
        cr = CaseReport(
            name="t", passed=True, status_code=200,
            duration_ms=10.0, error="",
        )
        with self.assertRaises(AttributeError):
            cr.name = "changed"  # type: ignore[misc]

    def test_suite_report_frozen(self) -> None:
        sr = SuiteReport(
            name="s", passed=True, total=0, passed_count=0,
            failed_count=0, duration_ms=0.0, avg_duration_ms=0.0,
            min_duration_ms=0.0, max_duration_ms=0.0,
        )
        with self.assertRaises(AttributeError):
            sr.name = "changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
