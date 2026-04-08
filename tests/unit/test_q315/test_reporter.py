"""Tests for lidco.coverage.reporter — CoverageReporter."""

from __future__ import annotations

import json
import unittest

from lidco.coverage.analyzer import AnalysisResult, CoverageAnalyzer
from lidco.coverage.collector import (
    BranchCoverage,
    CoverageSnapshot,
    FileCoverage,
    FunctionCoverage,
    LineCoverage,
)
from lidco.coverage.reporter import (
    CoverageReporter,
    ThresholdResult,
    TrendPoint,
    TrendReport,
)


def _make_analysis() -> AnalysisResult:
    """Create a realistic analysis result."""
    f1 = FileCoverage(
        path="src/a.py",
        lines=tuple(LineCoverage(i, 1 if i <= 8 else 0) for i in range(1, 11)),
        functions=(
            FunctionCoverage("fn_a", 1, 5, 2),
            FunctionCoverage("fn_b", 6, 10, 0),
        ),
        branches=(
            BranchCoverage(3, 0, 1),
            BranchCoverage(3, 1, 0),
        ),
    )
    snap = CoverageSnapshot(files=(f1,))
    analyzer = CoverageAnalyzer()
    return analyzer.analyze(snap)


class TestThresholdResult(unittest.TestCase):
    def test_frozen(self) -> None:
        tr = ThresholdResult(
            passed=True,
            line_rate=0.9,
            line_threshold=0.8,
            branch_rate=0.7,
            branch_threshold=0.7,
            function_rate=0.8,
            function_threshold=0.8,
        )
        self.assertTrue(tr.passed)
        with self.assertRaises(AttributeError):
            tr.passed = False  # type: ignore[misc]


class TestTrendReport(unittest.TestCase):
    def test_direction_improving(self) -> None:
        points = (
            TrendPoint("t1", 0.5, 0.4, 0.5, 100),
            TrendPoint("t2", 0.7, 0.6, 0.7, 120),
        )
        tr = TrendReport(points=points)
        self.assertEqual(tr.direction, "improving")
        self.assertAlmostEqual(tr.latest_rate, 0.7)

    def test_direction_declining(self) -> None:
        points = (
            TrendPoint("t1", 0.8, 0.7, 0.8, 100),
            TrendPoint("t2", 0.6, 0.5, 0.6, 100),
        )
        tr = TrendReport(points=points)
        self.assertEqual(tr.direction, "declining")

    def test_direction_stable(self) -> None:
        points = (
            TrendPoint("t1", 0.8, 0.7, 0.8, 100),
            TrendPoint("t2", 0.805, 0.7, 0.8, 100),
        )
        tr = TrendReport(points=points)
        self.assertEqual(tr.direction, "stable")

    def test_single_point(self) -> None:
        tr = TrendReport(points=(TrendPoint("t1", 0.8, 0.7, 0.8, 100),))
        self.assertEqual(tr.direction, "stable")

    def test_empty(self) -> None:
        tr = TrendReport()
        self.assertEqual(tr.direction, "stable")
        self.assertAlmostEqual(tr.latest_rate, 0.0)


class TestCheckThresholds(unittest.TestCase):
    def test_passes(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter(
            line_threshold=0.5,
            branch_threshold=0.3,
            function_threshold=0.3,
        )
        result = reporter.check_thresholds(analysis)
        self.assertTrue(result.passed)
        self.assertEqual(len(result.failures), 0)

    def test_fails_line(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter(line_threshold=0.95)
        result = reporter.check_thresholds(analysis)
        self.assertFalse(result.passed)
        self.assertTrue(any("Line coverage" in f for f in result.failures))

    def test_fails_branch(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter(branch_threshold=0.99)
        result = reporter.check_thresholds(analysis)
        self.assertFalse(result.passed)
        self.assertTrue(any("Branch coverage" in f for f in result.failures))

    def test_fails_function(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter(function_threshold=0.99)
        result = reporter.check_thresholds(analysis)
        self.assertFalse(result.passed)
        self.assertTrue(any("Function coverage" in f for f in result.failures))


class TestReportText(unittest.TestCase):
    def test_contains_summary(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter(line_threshold=0.5)
        text = reporter.report_text(analysis)
        self.assertIn("Coverage Report", text)
        self.assertIn("Overall line rate:", text)
        self.assertIn("src/a.py", text)

    def test_contains_uncovered(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter()
        text = reporter.report_text(analysis)
        self.assertIn("fn_b", text)

    def test_threshold_passed_text(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter(
            line_threshold=0.1,
            branch_threshold=0.1,
            function_threshold=0.1,
        )
        text = reporter.report_text(analysis)
        self.assertIn("PASSED", text)

    def test_threshold_failed_text(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter(line_threshold=0.99)
        text = reporter.report_text(analysis)
        self.assertIn("FAILED", text)


class TestReportJson(unittest.TestCase):
    def test_valid_json(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter()
        raw = reporter.report_json(analysis)
        obj = json.loads(raw)
        self.assertIn("overall", obj)
        self.assertIn("files", obj)
        self.assertIn("threshold", obj)
        self.assertIn("uncovered_functions", obj)
        self.assertIn("gaps", obj)

    def test_overall_values(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter()
        obj = json.loads(reporter.report_json(analysis))
        self.assertAlmostEqual(obj["overall"]["line_rate"], 0.8)
        self.assertIn("risk", obj["overall"])


class TestReportHtml(unittest.TestCase):
    def test_html_structure(self) -> None:
        analysis = _make_analysis()
        reporter = CoverageReporter()
        html = reporter.report_html(analysis)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<h1>Coverage Report</h1>", html)
        self.assertIn("src/a.py", html)
        self.assertIn("<table", html)


class TestBuildTrend(unittest.TestCase):
    def test_trend_from_snapshots(self) -> None:
        s1 = CoverageSnapshot(
            files=(
                FileCoverage(
                    path="a.py",
                    lines=(LineCoverage(1, 1), LineCoverage(2, 0)),
                ),
            ),
            timestamp="t1",
        )
        s2 = CoverageSnapshot(
            files=(
                FileCoverage(
                    path="a.py",
                    lines=(LineCoverage(1, 1), LineCoverage(2, 1)),
                ),
            ),
            timestamp="t2",
        )
        reporter = CoverageReporter()
        trend = reporter.build_trend([s1, s2])
        self.assertEqual(len(trend.points), 2)
        self.assertEqual(trend.direction, "improving")
        self.assertAlmostEqual(trend.points[0].line_rate, 0.5)
        self.assertAlmostEqual(trend.points[1].line_rate, 1.0)

    def test_trend_empty(self) -> None:
        reporter = CoverageReporter()
        trend = reporter.build_trend([])
        self.assertEqual(len(trend.points), 0)


if __name__ == "__main__":
    unittest.main()
