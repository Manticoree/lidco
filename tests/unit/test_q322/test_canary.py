"""Tests for lidco.deploy.canary — CanaryDeployer."""

from __future__ import annotations

import unittest

from lidco.deploy.canary import (
    CanaryConfig,
    CanaryDeployer,
    CanaryDeployment,
    CanaryMetrics,
    CanaryState,
    TrafficSplit,
)


class TestCanaryState(unittest.TestCase):
    def test_values(self) -> None:
        self.assertIn("promoted", [s.value for s in CanaryState])
        self.assertIn("rolled_back", [s.value for s in CanaryState])


class TestCanaryMetrics(unittest.TestCase):
    def test_defaults(self) -> None:
        m = CanaryMetrics()
        self.assertTrue(m.healthy)
        self.assertEqual(m.error_rate, 0.0)

    def test_frozen(self) -> None:
        m = CanaryMetrics(error_rate=0.1)
        with self.assertRaises(AttributeError):
            m.error_rate = 0.2  # type: ignore[misc]


class TestTrafficSplit(unittest.TestCase):
    def test_complement(self) -> None:
        t = TrafficSplit(canary_pct=30.0)
        self.assertAlmostEqual(t.stable_pct, 70.0)

    def test_zero(self) -> None:
        t = TrafficSplit()
        self.assertAlmostEqual(t.canary_pct, 0.0)
        self.assertAlmostEqual(t.stable_pct, 100.0)


class TestCanaryDeployment(unittest.TestCase):
    def test_auto_id(self) -> None:
        d = CanaryDeployment(version="v1")
        self.assertTrue(len(d.deployment_id) > 0)

    def test_duration(self) -> None:
        d = CanaryDeployment(started_at=10.0, finished_at=10.2)
        self.assertAlmostEqual(d.duration_ms, 200.0, places=0)


class TestCanaryConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        c = CanaryConfig()
        self.assertEqual(c.steps, [5.0, 25.0, 50.0, 100.0])
        self.assertTrue(c.auto_promote)
        self.assertTrue(c.auto_rollback)


class TestCanaryDeployer(unittest.TestCase):
    def test_initial_state(self) -> None:
        cd = CanaryDeployer()
        self.assertIsNone(cd.current)
        self.assertEqual(len(cd.history), 0)

    def test_deploy_success(self) -> None:
        cd = CanaryDeployer()
        dep = cd.deploy("v1")
        self.assertEqual(dep.state, CanaryState.PROMOTED)
        self.assertEqual(dep.version, "v1")
        self.assertIsNone(cd.current)
        self.assertEqual(len(cd.history), 1)

    def test_deploy_custom_steps(self) -> None:
        config = CanaryConfig(steps=[10.0, 50.0, 100.0])
        cd = CanaryDeployer(config=config)
        dep = cd.deploy("v2")
        self.assertEqual(dep.state, CanaryState.PROMOTED)
        self.assertEqual(dep.steps_completed, 3)
        self.assertEqual(dep.total_steps, 3)

    def test_deploy_fn_fails(self) -> None:
        cd = CanaryDeployer(deploy_fn=lambda _v, _p: False)
        dep = cd.deploy("v1")
        self.assertEqual(dep.state, CanaryState.FAILED)

    def test_deploy_fn_raises(self) -> None:
        def bad(_v, _p):
            raise RuntimeError("deploy error")

        cd = CanaryDeployer(deploy_fn=bad)
        dep = cd.deploy("v1")
        self.assertEqual(dep.state, CanaryState.FAILED)
        self.assertIn("deploy error", dep.error)

    def test_unhealthy_metrics_auto_rollback(self) -> None:
        bad_metrics = CanaryMetrics(error_rate=0.5, healthy=False)
        cd = CanaryDeployer(
            config=CanaryConfig(auto_rollback=True),
            metrics_fn=lambda _v: bad_metrics,
        )
        dep = cd.deploy("v1")
        self.assertEqual(dep.state, CanaryState.ROLLED_BACK)

    def test_unhealthy_no_auto_rollback(self) -> None:
        bad_metrics = CanaryMetrics(error_rate=0.5, healthy=False)
        cd = CanaryDeployer(
            config=CanaryConfig(auto_rollback=False),
            metrics_fn=lambda _v: bad_metrics,
        )
        dep = cd.deploy("v1")
        self.assertEqual(dep.state, CanaryState.FAILED)

    def test_latency_threshold(self) -> None:
        slow = CanaryMetrics(latency_p99_ms=999.0)
        cd = CanaryDeployer(
            config=CanaryConfig(latency_threshold_ms=500.0, auto_rollback=True),
            metrics_fn=lambda _v: slow,
        )
        dep = cd.deploy("v1")
        self.assertEqual(dep.state, CanaryState.ROLLED_BACK)

    def test_manual_rollback_no_current(self) -> None:
        cd = CanaryDeployer()
        self.assertIsNone(cd.rollback())

    def test_status_idle(self) -> None:
        cd = CanaryDeployer()
        s = cd.status()
        self.assertEqual(s["state"], "idle")

    def test_status_during_deploy(self) -> None:
        # We can check status on a completed deploy (current is cleared)
        cd = CanaryDeployer()
        cd.deploy("v1")
        s = cd.status()
        self.assertEqual(s["state"], "idle")

    def test_metrics_history(self) -> None:
        cd = CanaryDeployer()
        dep = cd.deploy("v1")
        # one metric per step
        self.assertEqual(len(dep.metrics_history), len(cd.config.steps))

    def test_config_property(self) -> None:
        cfg = CanaryConfig(steps=[10.0, 100.0])
        cd = CanaryDeployer(config=cfg)
        self.assertEqual(cd.config.steps, [10.0, 100.0])

    def test_deploy_logs(self) -> None:
        cd = CanaryDeployer()
        dep = cd.deploy("v1")
        self.assertTrue(any("v1" in log for log in dep.logs))


if __name__ == "__main__":
    unittest.main()
