"""Tests for lidco.deploy.rolling — RollingDeployer."""

from __future__ import annotations

import unittest

from lidco.deploy.rolling import (
    BatchResult,
    InstanceHealth,
    RollingConfig,
    RollingDeployer,
    RollingDeployment,
    RollingState,
)


class TestRollingState(unittest.TestCase):
    def test_values(self) -> None:
        states = [s.value for s in RollingState]
        self.assertIn("in_progress", states)
        self.assertIn("paused", states)
        self.assertIn("completed", states)
        self.assertIn("rolled_back", states)


class TestInstanceHealth(unittest.TestCase):
    def test_frozen(self) -> None:
        h = InstanceHealth(instance_id="i1", healthy=True)
        self.assertTrue(h.healthy)
        with self.assertRaises(AttributeError):
            h.healthy = False  # type: ignore[misc]


class TestBatchResult(unittest.TestCase):
    def test_defaults(self) -> None:
        b = BatchResult(batch_index=0)
        self.assertTrue(b.success)
        self.assertEqual(b.error, "")


class TestRollingConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        c = RollingConfig()
        self.assertEqual(c.batch_size, 1)
        self.assertTrue(c.pause_on_error)


class TestRollingDeployment(unittest.TestCase):
    def test_auto_id(self) -> None:
        d = RollingDeployment()
        self.assertTrue(len(d.deployment_id) > 0)

    def test_progress_pct(self) -> None:
        d = RollingDeployment(total_instances=10, updated_instances=5)
        self.assertAlmostEqual(d.progress_pct, 50.0)

    def test_progress_pct_zero(self) -> None:
        d = RollingDeployment(total_instances=0)
        self.assertEqual(d.progress_pct, 0.0)

    def test_duration(self) -> None:
        d = RollingDeployment(started_at=1.0, finished_at=1.5)
        self.assertAlmostEqual(d.duration_ms, 500.0)


class TestRollingDeployer(unittest.TestCase):
    def test_initial_state(self) -> None:
        rd = RollingDeployer()
        self.assertIsNone(rd.current)
        self.assertEqual(len(rd.history), 0)

    def test_deploy_success(self) -> None:
        instances = ["i1", "i2", "i3"]
        rd = RollingDeployer()
        dep = rd.deploy("v1", instances)
        self.assertEqual(dep.state, RollingState.COMPLETED)
        self.assertEqual(dep.updated_instances, 3)
        self.assertEqual(dep.total_instances, 3)
        self.assertAlmostEqual(dep.progress_pct, 100.0)

    def test_deploy_batch_size(self) -> None:
        config = RollingConfig(batch_size=2)
        rd = RollingDeployer(config=config)
        dep = rd.deploy("v1", ["i1", "i2", "i3", "i4"])
        self.assertEqual(dep.state, RollingState.COMPLETED)
        self.assertEqual(len(dep.batches), 2)

    def test_deploy_fn_fails_pause(self) -> None:
        call_count = 0

        def deploy_fn(inst, ver):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return False
            return True

        config = RollingConfig(batch_size=1, pause_on_error=True)
        rd = RollingDeployer(config=config, deploy_fn=deploy_fn)
        dep = rd.deploy("v1", ["i1", "i2", "i3"])
        self.assertEqual(dep.state, RollingState.PAUSED)
        self.assertEqual(dep.updated_instances, 1)

    def test_deploy_fn_fails_no_pause(self) -> None:
        config = RollingConfig(pause_on_error=False)
        rd = RollingDeployer(config=config, deploy_fn=lambda _i, _v: False)
        dep = rd.deploy("v1", ["i1"])
        self.assertEqual(dep.state, RollingState.FAILED)

    def test_deploy_fn_raises(self) -> None:
        def bad(_i, _v):
            raise RuntimeError("boom")

        config = RollingConfig(pause_on_error=False)
        rd = RollingDeployer(config=config, deploy_fn=bad)
        dep = rd.deploy("v1", ["i1"])
        self.assertEqual(dep.state, RollingState.FAILED)

    def test_health_check_fails(self) -> None:
        config = RollingConfig(health_retries=1, health_interval_s=0, pause_on_error=False)
        rd = RollingDeployer(
            config=config,
            health_fn=lambda inst: InstanceHealth(instance_id=inst, healthy=False),
        )
        dep = rd.deploy("v1", ["i1"])
        self.assertEqual(dep.state, RollingState.FAILED)

    def test_resume(self) -> None:
        call_count = 0

        def deploy_fn(inst, ver):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return False
            return True

        config = RollingConfig(batch_size=1, pause_on_error=True)
        rd = RollingDeployer(config=config, deploy_fn=deploy_fn)
        dep = rd.deploy("v1", ["i1", "i2", "i3"])
        self.assertEqual(dep.state, RollingState.PAUSED)

        # Fix the deploy_fn and resume
        rd._deploy_fn = lambda _i, _v: True
        dep2 = rd.resume(["i1", "i2", "i3"])
        self.assertIsNotNone(dep2)
        self.assertEqual(dep2.state, RollingState.COMPLETED)

    def test_resume_no_paused(self) -> None:
        rd = RollingDeployer()
        self.assertIsNone(rd.resume(["i1"]))

    def test_rollback(self) -> None:
        rd = RollingDeployer()
        dep = rd.rollback(["i1", "i2"], "v0")
        self.assertIsNotNone(dep)
        self.assertEqual(dep.state, RollingState.ROLLED_BACK)

    def test_rollback_partial_fail(self) -> None:
        count = 0

        def bad_rollback(inst, ver):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError("fail")
            return True

        rd = RollingDeployer(rollback_fn=bad_rollback)
        dep = rd.rollback(["i1", "i2"], "v0")
        self.assertEqual(dep.state, RollingState.FAILED)

    def test_status_idle(self) -> None:
        rd = RollingDeployer()
        s = rd.status()
        self.assertEqual(s["state"], "idle")

    def test_config_property(self) -> None:
        cfg = RollingConfig(batch_size=5)
        rd = RollingDeployer(config=cfg)
        self.assertEqual(rd.config.batch_size, 5)

    def test_deploy_logs(self) -> None:
        rd = RollingDeployer()
        dep = rd.deploy("v1", ["i1"])
        self.assertTrue(len(dep.logs) > 0)

    def test_history(self) -> None:
        rd = RollingDeployer()
        rd.deploy("v1", ["i1"])
        rd.deploy("v2", ["i1"])
        self.assertEqual(len(rd.history), 2)


if __name__ == "__main__":
    unittest.main()
