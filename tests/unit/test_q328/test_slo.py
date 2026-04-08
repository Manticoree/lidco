"""Tests for lidco.sre.slo — SLO Tracker."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.sre.slo import (
    BudgetStatus,
    BurnRateAlert,
    BurnRateSeverity,
    SLI,
    SLO,
    SLOError,
    SLOReport,
    SLOTracker,
)


class TestSLODataclasses(unittest.TestCase):
    def test_slo_defaults(self) -> None:
        slo = SLO(name="api-availability", sli_name="api-requests")
        self.assertEqual(slo.target, 0.999)
        self.assertEqual(slo.window_seconds, 30 * 24 * 3600)
        self.assertTrue(len(slo.id) > 0)

    def test_slo_error_budget_fraction(self) -> None:
        slo = SLO(target=0.99)
        self.assertAlmostEqual(slo.error_budget_fraction(), 0.01)

    def test_slo_error_budget_minutes(self) -> None:
        slo = SLO(target=0.99, window_seconds=86400)  # 1 day
        expected = (86400 / 60.0) * 0.01  # 14.4 min
        self.assertAlmostEqual(slo.error_budget_minutes(), expected)

    def test_sli_defaults(self) -> None:
        sli = SLI(name="latency", value=0.95, good=True)
        self.assertEqual(sli.name, "latency")
        self.assertTrue(sli.good)
        self.assertIsInstance(sli.timestamp, float)

    def test_burn_rate_alert_defaults(self) -> None:
        alert = BurnRateAlert(slo_id="abc")
        self.assertEqual(alert.threshold, 1.0)
        self.assertEqual(alert.severity, BurnRateSeverity.MEDIUM)

    def test_budget_status_fields(self) -> None:
        status = BudgetStatus(
            slo_id="x", slo_name="test", target=0.99,
            total_events=100, bad_events=2,
            budget_total=1.0, budget_remaining=0.0,
            budget_consumed_fraction=0.5, burn_rate=0.5,
            is_healthy=True,
        )
        self.assertEqual(status.total_events, 100)
        self.assertTrue(status.is_healthy)

    def test_slo_report_summary(self) -> None:
        status = BudgetStatus(
            slo_id="x", slo_name="api", target=0.99,
            total_events=1000, bad_events=5,
            budget_total=10.0, budget_remaining=5.0,
            budget_consumed_fraction=0.5, burn_rate=0.5,
            is_healthy=True,
        )
        report = SLOReport(statuses=[status])
        summary = report.summary()
        self.assertIn("api", summary)
        self.assertIn("HEALTHY", summary)
        self.assertIn("50.0%", summary)


class TestSLOTracker(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = SLOTracker()

    def test_define_slo(self) -> None:
        slo = self.tracker.define_slo(SLO(name="test", target=0.99, sli_name="req"))
        self.assertEqual(slo.name, "test")
        self.assertEqual(len(self.tracker.list_slos()), 1)

    def test_define_slo_no_name_raises(self) -> None:
        with self.assertRaises(SLOError):
            self.tracker.define_slo(SLO(name="", target=0.99))

    def test_define_slo_bad_target_raises(self) -> None:
        with self.assertRaises(SLOError):
            self.tracker.define_slo(SLO(name="x", target=1.5))
        with self.assertRaises(SLOError):
            self.tracker.define_slo(SLO(name="x", target=0.0))

    def test_get_slo(self) -> None:
        slo = self.tracker.define_slo(SLO(name="a", target=0.99, sli_name="a"))
        result = self.tracker.get_slo(slo.id)
        self.assertEqual(result.name, "a")

    def test_get_slo_not_found(self) -> None:
        with self.assertRaises(SLOError):
            self.tracker.get_slo("nonexistent")

    def test_remove_slo(self) -> None:
        slo = self.tracker.define_slo(SLO(name="rm", target=0.99, sli_name="rm"))
        self.tracker.remove_slo(slo.id)
        self.assertEqual(len(self.tracker.list_slos()), 0)

    def test_remove_slo_not_found(self) -> None:
        with self.assertRaises(SLOError):
            self.tracker.remove_slo("nope")

    def test_record_sli(self) -> None:
        self.tracker.record_sli(SLI(name="req", value=1.0, good=True))
        self.assertEqual(len(self.tracker.get_measurements()), 1)

    def test_record_event(self) -> None:
        sli = self.tracker.record_event("req", good=True, labels={"env": "prod"})
        self.assertTrue(sli.good)
        self.assertEqual(sli.labels, {"env": "prod"})

    def test_get_measurements_filter(self) -> None:
        self.tracker.record_event("a", True)
        self.tracker.record_event("b", False)
        self.assertEqual(len(self.tracker.get_measurements("a")), 1)

    def test_get_measurements_since(self) -> None:
        self.tracker.record_event("a", True)
        future = time.time() + 1000
        self.assertEqual(len(self.tracker.get_measurements(since=future)), 0)

    def test_budget_status_healthy(self) -> None:
        slo = self.tracker.define_slo(SLO(name="x", target=0.99, sli_name="x"))
        for _ in range(99):
            self.tracker.record_event("x", True)
        self.tracker.record_event("x", False)
        status = self.tracker.budget_status(slo.id)
        self.assertEqual(status.total_events, 100)
        self.assertEqual(status.bad_events, 1)
        self.assertTrue(status.is_healthy)

    def test_budget_status_unhealthy(self) -> None:
        slo = self.tracker.define_slo(SLO(name="y", target=0.99, sli_name="y"))
        # All bad events => budget consumed >> 1.0
        for _ in range(10):
            self.tracker.record_event("y", False)
        status = self.tracker.budget_status(slo.id)
        self.assertFalse(status.is_healthy)

    def test_add_alert(self) -> None:
        slo = self.tracker.define_slo(SLO(name="z", target=0.99, sli_name="z"))
        alert = self.tracker.add_alert(BurnRateAlert(slo_id=slo.id, threshold=2.0))
        self.assertEqual(len(self.tracker.list_alerts()), 1)
        self.assertEqual(alert.threshold, 2.0)

    def test_add_alert_bad_slo(self) -> None:
        with self.assertRaises(SLOError):
            self.tracker.add_alert(BurnRateAlert(slo_id="nonexistent"))

    def test_remove_alert(self) -> None:
        slo = self.tracker.define_slo(SLO(name="a", target=0.99, sli_name="a"))
        alert = self.tracker.add_alert(BurnRateAlert(slo_id=slo.id))
        self.tracker.remove_alert(alert.id)
        self.assertEqual(len(self.tracker.list_alerts()), 0)

    def test_remove_alert_not_found(self) -> None:
        with self.assertRaises(SLOError):
            self.tracker.remove_alert("nope")

    def test_alert_callback_fires(self) -> None:
        slo = self.tracker.define_slo(SLO(name="cb", target=0.99, sli_name="cb"))
        self.tracker.add_alert(BurnRateAlert(slo_id=slo.id, threshold=0.0))  # always fires
        fired: list[tuple] = []
        self.tracker.on_alert(lambda a, s: fired.append((a, s)))
        self.tracker.record_event("cb", False)
        self.assertTrue(len(fired) > 0)

    def test_report(self) -> None:
        slo = self.tracker.define_slo(SLO(name="rpt", target=0.99, sli_name="rpt"))
        self.tracker.record_event("rpt", True)
        report = self.tracker.report()
        self.assertEqual(len(report.statuses), 1)
        self.assertIn("rpt", report.summary())

    def test_report_specific_ids(self) -> None:
        slo1 = self.tracker.define_slo(SLO(name="a", target=0.99, sli_name="a"))
        slo2 = self.tracker.define_slo(SLO(name="b", target=0.99, sli_name="b"))
        report = self.tracker.report(slo_ids=[slo1.id])
        self.assertEqual(len(report.statuses), 1)


if __name__ == "__main__":
    unittest.main()
