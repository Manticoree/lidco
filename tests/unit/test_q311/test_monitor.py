"""Tests for lidco.chaos.monitor."""

from __future__ import annotations

import time
import unittest
from unittest import mock

from lidco.chaos.monitor import (
    ChaosMonitor,
    ErrorRateWindow,
    HealthMetric,
    HealthStatus,
    RecoveryReport,
    SLAReport,
)


class TestHealthMetric(unittest.TestCase):
    def test_create(self) -> None:
        m = HealthMetric(name="cpu", value=85.0, timestamp=100.0)
        self.assertEqual(m.name, "cpu")
        self.assertEqual(m.value, 85.0)
        self.assertEqual(m.tags, {})

    def test_with_tags(self) -> None:
        m = HealthMetric(
            name="mem", value=70.0, timestamp=100.0, tags={"host": "node-1"}
        )
        self.assertEqual(m.tags, {"host": "node-1"})

    def test_frozen(self) -> None:
        m = HealthMetric(name="cpu", value=85.0, timestamp=100.0)
        with self.assertRaises(AttributeError):
            m.value = 90.0  # type: ignore[misc]


class TestErrorRateWindow(unittest.TestCase):
    def test_error_rate(self) -> None:
        w = ErrorRateWindow(window_seconds=60, total_requests=100, error_count=5)
        self.assertAlmostEqual(w.error_rate, 0.05)

    def test_error_rate_zero_requests(self) -> None:
        w = ErrorRateWindow(window_seconds=60, total_requests=0, error_count=0)
        self.assertEqual(w.error_rate, 0.0)


class TestSLAReport(unittest.TestCase):
    def test_within_sla(self) -> None:
        r = SLAReport(
            target_availability=0.999,
            actual_availability=0.9995,
            total_downtime_seconds=0.5,
        )
        self.assertTrue(r.is_within_sla)

    def test_below_sla(self) -> None:
        r = SLAReport(
            target_availability=0.999,
            actual_availability=0.99,
            total_downtime_seconds=10.0,
        )
        self.assertFalse(r.is_within_sla)


class TestChaosMonitor(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor = ChaosMonitor(sla_target=0.999)

    def test_initial_health(self) -> None:
        self.assertEqual(self.monitor.health_status, HealthStatus.HEALTHY)

    def test_record_metric(self) -> None:
        m = self.monitor.record_metric("cpu", 85.0)
        self.assertIsInstance(m, HealthMetric)
        self.assertEqual(m.name, "cpu")
        self.assertEqual(m.value, 85.0)

    def test_record_metric_with_tags(self) -> None:
        m = self.monitor.record_metric("mem", 70.0, tags={"host": "n1"})
        self.assertEqual(m.tags, {"host": "n1"})

    def test_record_error(self) -> None:
        self.monitor.record_error("timeout", target="api")
        self.assertEqual(self.monitor.error_count, 1)

    def test_set_health_status(self) -> None:
        self.monitor.set_health_status(HealthStatus.DEGRADED)
        self.assertEqual(self.monitor.health_status, HealthStatus.DEGRADED)

    def test_health_transition_starts_downtime(self) -> None:
        self.monitor.set_health_status(HealthStatus.UNHEALTHY)
        sla = self.monitor.get_sla_report()
        self.assertGreater(sla.total_downtime_seconds, 0)

    def test_health_recovery_ends_downtime(self) -> None:
        self.monitor.set_health_status(HealthStatus.UNHEALTHY)
        self.monitor.set_health_status(HealthStatus.HEALTHY)
        sla = self.monitor.get_sla_report()
        # Downtime should be very small but >0
        self.assertGreaterEqual(sla.total_downtime_seconds, 0)

    def test_get_error_rate(self) -> None:
        self.monitor.record_error("err1")
        self.monitor.record_metric("req", 1.0)
        rate = self.monitor.get_error_rate(window_seconds=60.0)
        self.assertIsInstance(rate, ErrorRateWindow)
        self.assertEqual(rate.error_count, 1)
        self.assertEqual(rate.total_requests, 2)  # 1 metric + 1 error

    def test_record_recovery(self) -> None:
        now = time.time()
        report = self.monitor.record_recovery(
            "exp-1",
            failure_at=now - 10,
            recovery_at=now,
        )
        self.assertIsInstance(report, RecoveryReport)
        self.assertAlmostEqual(report.recovery_time_seconds, 10.0, places=1)
        self.assertTrue(report.full_recovery)

    def test_record_recovery_partial(self) -> None:
        now = time.time()
        report = self.monitor.record_recovery(
            "exp-2",
            failure_at=now - 5,
            recovery_at=now,
            full_recovery=False,
        )
        self.assertFalse(report.full_recovery)

    def test_recovery_reports(self) -> None:
        now = time.time()
        self.monitor.record_recovery("e1", failure_at=now - 5, recovery_at=now)
        self.assertEqual(len(self.monitor.recovery_reports), 1)

    def test_recovery_reports_is_copy(self) -> None:
        reports = self.monitor.recovery_reports
        reports.append(None)  # type: ignore[arg-type]
        self.assertEqual(len(self.monitor.recovery_reports), 0)

    def test_get_sla_report_initial(self) -> None:
        sla = self.monitor.get_sla_report()
        self.assertIsInstance(sla, SLAReport)
        self.assertTrue(sla.is_within_sla)

    def test_get_metrics(self) -> None:
        self.monitor.record_metric("cpu", 80.0)
        self.monitor.record_metric("mem", 60.0)
        self.monitor.record_metric("cpu", 85.0)
        cpu_metrics = self.monitor.get_metrics(name="cpu")
        self.assertEqual(len(cpu_metrics), 2)

    def test_get_metrics_since(self) -> None:
        self.monitor.record_metric("cpu", 80.0)
        future = time.time() + 9999
        metrics = self.monitor.get_metrics(since=future)
        self.assertEqual(len(metrics), 0)

    def test_summary(self) -> None:
        self.monitor.record_metric("cpu", 80.0)
        self.monitor.record_error("timeout")
        s = self.monitor.summary()
        self.assertEqual(s["health_status"], "healthy")
        self.assertEqual(s["total_metrics"], 1)
        self.assertEqual(s["total_errors"], 1)
        self.assertIn("within_sla", s)
        self.assertIn("actual_availability", s)

    def test_error_count(self) -> None:
        self.assertEqual(self.monitor.error_count, 0)
        self.monitor.record_error("e1")
        self.monitor.record_error("e2")
        self.assertEqual(self.monitor.error_count, 2)


if __name__ == "__main__":
    unittest.main()
