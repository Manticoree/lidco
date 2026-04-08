"""Tests for lidco.flaky.dashboard — FlakyDashboard."""

from __future__ import annotations

import unittest

from lidco.flaky.dashboard import (
    DashboardReport,
    FlakeEntry,
    FlakyDashboard,
    TrendPoint,
)
from lidco.flaky.detector import FlakyTestResult, FlakySeverity
from lidco.flaky.quarantine import FlakyQuarantine


def _make_result(
    name: str,
    *,
    is_flaky: bool = True,
    fail_count: int = 5,
    total_runs: int = 10,
    pass_rate: float = 0.5,
    severity: FlakySeverity = FlakySeverity.MEDIUM,
) -> FlakyTestResult:
    return FlakyTestResult(
        test_name=name,
        total_runs=total_runs,
        pass_count=total_runs - fail_count,
        fail_count=fail_count,
        pass_rate=pass_rate,
        timing_variance=0.0,
        is_flaky=is_flaky,
        severity=severity,
    )


class TestFlakyDashboard(unittest.TestCase):
    def test_empty_results(self) -> None:
        d = FlakyDashboard()
        report = d.generate([])
        self.assertEqual(report.total_tests, 0)
        self.assertEqual(report.flaky_count, 0)
        self.assertEqual(report.flaky_rate, 0.0)

    def test_flaky_count(self) -> None:
        results = [
            _make_result("a", is_flaky=True),
            _make_result("b", is_flaky=False),
            _make_result("c", is_flaky=True),
        ]
        report = FlakyDashboard().generate(results)
        self.assertEqual(report.total_tests, 3)
        self.assertEqual(report.flaky_count, 2)

    def test_top_flakers_sorted(self) -> None:
        results = [
            _make_result("a", is_flaky=True, fail_count=3),
            _make_result("b", is_flaky=True, fail_count=8),
            _make_result("c", is_flaky=True, fail_count=5),
        ]
        report = FlakyDashboard().generate(results, top_n=2)
        self.assertEqual(len(report.top_flakers), 2)
        self.assertEqual(report.top_flakers[0].test_name, "b")
        self.assertEqual(report.top_flakers[1].test_name, "c")

    def test_trends(self) -> None:
        history = [
            ("2024-W01", 5, 100),
            ("2024-W02", 3, 100),
        ]
        report = FlakyDashboard().generate([], history=history)
        self.assertEqual(len(report.trends), 2)
        self.assertEqual(report.trends[0].period, "2024-W01")
        self.assertAlmostEqual(report.trends[0].flaky_rate, 0.05)

    def test_quarantine_stats(self) -> None:
        q = FlakyQuarantine()
        q.quarantine("a")
        q.quarantine("b")
        q.release("b")
        d = FlakyDashboard(quarantine=q)
        report = d.generate([])
        self.assertEqual(report.quarantine_active, 1)
        self.assertEqual(report.quarantine_released, 1)

    def test_team_breakdown(self) -> None:
        mapping = {"tests.unit.": "backend", "tests.e2e.": "frontend"}
        results = [
            _make_result("tests.unit.test_a", is_flaky=True),
            _make_result("tests.unit.test_b", is_flaky=True),
            _make_result("tests.e2e.test_c", is_flaky=True),
            _make_result("other", is_flaky=True),
        ]
        report = FlakyDashboard(team_mapping=mapping).generate(results)
        self.assertEqual(report.team_breakdown["backend"], 2)
        self.assertEqual(report.team_breakdown["frontend"], 1)
        self.assertEqual(report.team_breakdown["unassigned"], 1)

    def test_severity_breakdown(self) -> None:
        results = [
            _make_result("a", is_flaky=True, severity=FlakySeverity.HIGH),
            _make_result("b", is_flaky=True, severity=FlakySeverity.HIGH),
            _make_result("c", is_flaky=True, severity=FlakySeverity.LOW),
        ]
        report = FlakyDashboard().generate(results)
        self.assertEqual(report.severity_breakdown["high"], 2)
        self.assertEqual(report.severity_breakdown["low"], 1)

    def test_format_text(self) -> None:
        results = [
            _make_result("test_a", is_flaky=True, fail_count=5),
        ]
        d = FlakyDashboard()
        report = d.generate(results, top_n=5)
        text = d.format_text(report)
        self.assertIn("Flaky Test Dashboard", text)
        self.assertIn("test_a", text)
        self.assertIn("Total tests:", text)

    def test_format_text_with_trends(self) -> None:
        history = [("2024-W01", 2, 50)]
        d = FlakyDashboard()
        report = d.generate([], history=history)
        text = d.format_text(report)
        self.assertIn("Trends:", text)
        self.assertIn("2024-W01", text)

    def test_format_text_team_breakdown(self) -> None:
        results = [_make_result("a", is_flaky=True)]
        d = FlakyDashboard()
        report = d.generate(results)
        text = d.format_text(report)
        self.assertIn("Team Breakdown:", text)

    def test_format_text_severity_breakdown(self) -> None:
        results = [_make_result("a", is_flaky=True, severity=FlakySeverity.HIGH)]
        d = FlakyDashboard()
        report = d.generate(results)
        text = d.format_text(report)
        self.assertIn("Severity Breakdown:", text)

    def test_quarantine_overlay_in_top_flakers(self) -> None:
        q = FlakyQuarantine()
        q.quarantine("test_a")
        results = [_make_result("test_a", is_flaky=True)]
        d = FlakyDashboard(quarantine=q)
        report = d.generate(results)
        self.assertEqual(report.top_flakers[0].quarantine_status, "active")

    def test_no_quarantine_shows_none(self) -> None:
        results = [_make_result("test_a", is_flaky=True)]
        d = FlakyDashboard()
        report = d.generate(results)
        self.assertEqual(report.top_flakers[0].quarantine_status, "none")

    def test_flaky_rate_calculation(self) -> None:
        results = [
            _make_result("a", is_flaky=True),
            _make_result("b", is_flaky=True),
            _make_result("c", is_flaky=False),
            _make_result("d", is_flaky=False),
        ]
        report = FlakyDashboard().generate(results)
        self.assertAlmostEqual(report.flaky_rate, 0.5)

    def test_trend_zero_total(self) -> None:
        history = [("2024-W01", 0, 0)]
        report = FlakyDashboard().generate([], history=history)
        self.assertEqual(report.trends[0].flaky_rate, 0.0)


class TestFlakeEntry(unittest.TestCase):
    def test_defaults(self) -> None:
        e = FlakeEntry(
            test_name="t",
            fail_count=1,
            total_runs=10,
            pass_rate=0.9,
            severity="low",
        )
        self.assertEqual(e.quarantine_status, "none")
        self.assertEqual(e.team, "")


class TestTrendPoint(unittest.TestCase):
    def test_frozen(self) -> None:
        t = TrendPoint(period="w1", flaky_count=1, total_tests=10, flaky_rate=0.1)
        with self.assertRaises(AttributeError):
            t.period = "w2"  # type: ignore[misc]


class TestDashboardReport(unittest.TestCase):
    def test_defaults(self) -> None:
        r = DashboardReport(total_tests=0, flaky_count=0, flaky_rate=0.0)
        self.assertEqual(r.top_flakers, [])
        self.assertEqual(r.trends, [])
        self.assertEqual(r.team_breakdown, {})


if __name__ == "__main__":
    unittest.main()
