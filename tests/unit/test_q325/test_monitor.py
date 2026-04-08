"""Tests for lidco.envmgmt.monitor — EnvMonitor."""

from __future__ import annotations

import time
import unittest

from lidco.envmgmt.monitor import (
    CostEstimate,
    EnvMonitor,
    HealthReport,
    HealthStatus,
    ResourceUsage,
)
from lidco.envmgmt.provisioner import EnvProvisioner, EnvStatus, EnvTemplate, EnvTier


def _provision(name: str, tier: EnvTier, config: dict | None = None):
    p = EnvProvisioner()
    tmpl = EnvTemplate(name=name, tier=tier, config=config or {})
    p.register_template(tmpl)
    return p.provision(name)


class TestResourceUsage(unittest.TestCase):
    def test_defaults(self) -> None:
        u = ResourceUsage()
        self.assertEqual(u.cpu_percent, 0.0)
        self.assertEqual(u.memory_percent, 0.0)

    def test_custom(self) -> None:
        u = ResourceUsage(cpu_percent=55.0, memory_percent=70.0, disk_percent=30.0)
        self.assertEqual(u.cpu_percent, 55.0)


class TestCostEstimate(unittest.TestCase):
    def test_defaults(self) -> None:
        c = CostEstimate()
        self.assertEqual(c.hourly, 0.0)
        self.assertEqual(c.currency, "USD")


class TestEnvMonitor(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor = EnvMonitor()
        self.env = _provision("test-env", EnvTier.DEV, {"replicas": 2})

    # -- Resource snapshots ---------------------------------------------------

    def test_record_and_get_usage(self) -> None:
        u = ResourceUsage(cpu_percent=50.0)
        self.monitor.record_usage(self.env.env_id, u)
        got = self.monitor.get_usage(self.env.env_id)
        self.assertEqual(got.cpu_percent, 50.0)

    def test_get_usage_missing(self) -> None:
        self.assertIsNone(self.monitor.get_usage("nope"))

    # -- Baseline / drift -----------------------------------------------------

    def test_no_drift_without_baseline(self) -> None:
        drifted, keys = self.monitor.detect_drift(self.env)
        self.assertFalse(drifted)
        self.assertEqual(keys, [])

    def test_no_drift_matching_baseline(self) -> None:
        self.monitor.set_baseline(self.env.env_id, dict(self.env.config))
        drifted, keys = self.monitor.detect_drift(self.env)
        self.assertFalse(drifted)

    def test_drift_detected(self) -> None:
        self.monitor.set_baseline(self.env.env_id, dict(self.env.config))
        self.env.config["replicas"] = 99
        drifted, keys = self.monitor.detect_drift(self.env)
        self.assertTrue(drifted)
        self.assertIn("replicas", keys)

    def test_drift_added_key(self) -> None:
        self.monitor.set_baseline(self.env.env_id, dict(self.env.config))
        self.env.config["new_key"] = "val"
        drifted, keys = self.monitor.detect_drift(self.env)
        self.assertTrue(drifted)
        self.assertIn("new_key", keys)

    # -- Expiry ---------------------------------------------------------------

    def test_no_expiry(self) -> None:
        self.assertIsNone(self.monitor.time_until_expiry(self.env.env_id))

    def test_expiry_future(self) -> None:
        future = time.time() + 3600
        self.monitor.set_expiry(self.env.env_id, future)
        remaining = self.monitor.time_until_expiry(self.env.env_id)
        self.assertGreater(remaining, 0)

    def test_expiry_past(self) -> None:
        past = time.time() - 100
        self.monitor.set_expiry(self.env.env_id, past)
        remaining = self.monitor.time_until_expiry(self.env.env_id)
        self.assertEqual(remaining, 0.0)

    def test_get_expired_envs(self) -> None:
        past = time.time() - 100
        self.monitor.set_expiry(self.env.env_id, past)
        expired = self.monitor.get_expired_envs([self.env])
        self.assertEqual(len(expired), 1)

    def test_get_expired_envs_not_expired(self) -> None:
        future = time.time() + 3600
        self.monitor.set_expiry(self.env.env_id, future)
        expired = self.monitor.get_expired_envs([self.env])
        self.assertEqual(len(expired), 0)

    def test_get_expired_envs_destroyed_ignored(self) -> None:
        past = time.time() - 100
        self.monitor.set_expiry(self.env.env_id, past)
        self.env.status = EnvStatus.DESTROYED
        expired = self.monitor.get_expired_envs([self.env])
        self.assertEqual(len(expired), 0)

    # -- Cost estimation ------------------------------------------------------

    def test_cost_dev(self) -> None:
        cost = self.monitor.estimate_cost(self.env)
        # 2 replicas * 0.05 = 0.10/hr
        self.assertAlmostEqual(cost.hourly, 0.10, places=4)
        self.assertAlmostEqual(cost.daily, 2.4, places=4)

    def test_cost_prod(self) -> None:
        env = _provision("prod", EnvTier.PROD, {"replicas": 3})
        cost = self.monitor.estimate_cost(env)
        self.assertAlmostEqual(cost.hourly, 1.50, places=4)

    def test_cost_default_replicas(self) -> None:
        env = _provision("bare", EnvTier.DEV, {})
        # default replicas=1 from auto-config
        cost = self.monitor.estimate_cost(env)
        self.assertAlmostEqual(cost.hourly, 0.05, places=4)

    # -- Health check ---------------------------------------------------------

    def test_health_healthy(self) -> None:
        report = self.monitor.check_health(self.env)
        self.assertIsInstance(report, HealthReport)
        self.assertEqual(report.status, HealthStatus.HEALTHY)
        self.assertEqual(report.warnings, [])

    def test_health_cpu_warning(self) -> None:
        self.monitor.record_usage(
            self.env.env_id, ResourceUsage(cpu_percent=75.0)
        )
        report = self.monitor.check_health(self.env)
        self.assertEqual(report.status, HealthStatus.WARNING)
        self.assertTrue(any("CPU" in w for w in report.warnings))

    def test_health_cpu_critical(self) -> None:
        self.monitor.record_usage(
            self.env.env_id, ResourceUsage(cpu_percent=95.0)
        )
        report = self.monitor.check_health(self.env)
        self.assertEqual(report.status, HealthStatus.CRITICAL)

    def test_health_memory_warning(self) -> None:
        self.monitor.record_usage(
            self.env.env_id, ResourceUsage(memory_percent=80.0)
        )
        report = self.monitor.check_health(self.env)
        self.assertEqual(report.status, HealthStatus.WARNING)

    def test_health_memory_critical(self) -> None:
        self.monitor.record_usage(
            self.env.env_id, ResourceUsage(memory_percent=96.0)
        )
        report = self.monitor.check_health(self.env)
        self.assertEqual(report.status, HealthStatus.CRITICAL)

    def test_health_disk_warning(self) -> None:
        self.monitor.record_usage(
            self.env.env_id, ResourceUsage(disk_percent=85.0)
        )
        report = self.monitor.check_health(self.env)
        self.assertEqual(report.status, HealthStatus.WARNING)

    def test_health_disk_critical(self) -> None:
        self.monitor.record_usage(
            self.env.env_id, ResourceUsage(disk_percent=96.0)
        )
        report = self.monitor.check_health(self.env)
        self.assertEqual(report.status, HealthStatus.CRITICAL)

    def test_health_drift_detected(self) -> None:
        self.monitor.set_baseline(self.env.env_id, {"replicas": 1})
        report = self.monitor.check_health(self.env)
        self.assertTrue(report.drift_detected)
        self.assertTrue(any("drift" in w.lower() for w in report.warnings))

    def test_health_inactive_env(self) -> None:
        self.env.status = EnvStatus.DESTROYED
        report = self.monitor.check_health(self.env)
        self.assertEqual(report.status, HealthStatus.CRITICAL)

    def test_health_expired_env(self) -> None:
        self.monitor.set_expiry(self.env.env_id, time.time() - 100)
        report = self.monitor.check_health(self.env)
        self.assertTrue(any("expired" in w.lower() for w in report.warnings))

    def test_health_uptime(self) -> None:
        report = self.monitor.check_health(self.env)
        self.assertGreater(report.uptime_seconds, 0)

    def test_set_thresholds(self) -> None:
        self.monitor.set_thresholds({"cpu_warning": 50.0})
        self.monitor.record_usage(
            self.env.env_id, ResourceUsage(cpu_percent=55.0)
        )
        report = self.monitor.check_health(self.env)
        self.assertEqual(report.status, HealthStatus.WARNING)

    def test_health_report_fields(self) -> None:
        report = self.monitor.check_health(self.env)
        self.assertEqual(report.env_id, self.env.env_id)
        self.assertEqual(report.env_name, self.env.name)
        self.assertIsInstance(report.cost, CostEstimate)
        self.assertIsInstance(report.resource_usage, ResourceUsage)


class TestHealthStatus(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(HealthStatus.HEALTHY.value, "healthy")
        self.assertEqual(HealthStatus.CRITICAL.value, "critical")
        self.assertEqual(HealthStatus.UNKNOWN.value, "unknown")


if __name__ == "__main__":
    unittest.main()
