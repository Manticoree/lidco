"""Tests for lidco.deploy.blue_green — BlueGreenDeployer."""

from __future__ import annotations

import unittest

from lidco.deploy.blue_green import (
    BlueGreenDeployer,
    BlueGreenDeployment,
    DeploymentState,
    HealthCheckResult,
    SlotColor,
    SlotInfo,
)


class TestSlotColor(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(SlotColor.BLUE.value, "blue")
        self.assertEqual(SlotColor.GREEN.value, "green")


class TestDeploymentState(unittest.TestCase):
    def test_all_states(self) -> None:
        states = [s.value for s in DeploymentState]
        self.assertIn("idle", states)
        self.assertIn("live", states)
        self.assertIn("rolling_back", states)
        self.assertIn("failed", states)


class TestHealthCheckResult(unittest.TestCase):
    def test_frozen(self) -> None:
        r = HealthCheckResult(healthy=True, latency_ms=5.0, detail="ok")
        self.assertTrue(r.healthy)
        self.assertEqual(r.latency_ms, 5.0)
        with self.assertRaises(AttributeError):
            r.healthy = False  # type: ignore[misc]


class TestSlotInfo(unittest.TestCase):
    def test_defaults(self) -> None:
        s = SlotInfo(color=SlotColor.BLUE)
        self.assertEqual(s.version, "")
        self.assertFalse(s.healthy)


class TestBlueGreenDeployment(unittest.TestCase):
    def test_auto_id(self) -> None:
        d = BlueGreenDeployment(version="v1")
        self.assertTrue(len(d.deployment_id) > 0)

    def test_duration_ms(self) -> None:
        d = BlueGreenDeployment(started_at=100.0, finished_at=100.5)
        self.assertAlmostEqual(d.duration_ms, 500.0, places=0)

    def test_duration_zero_if_not_finished(self) -> None:
        d = BlueGreenDeployment(started_at=100.0)
        self.assertEqual(d.duration_ms, 0.0)


class TestBlueGreenDeployer(unittest.TestCase):
    def test_initial_state(self) -> None:
        bg = BlueGreenDeployer()
        self.assertEqual(bg.active_slot, SlotColor.BLUE)
        self.assertEqual(bg.inactive_slot, SlotColor.GREEN)
        self.assertEqual(len(bg.history), 0)

    def test_deploy_success_default(self) -> None:
        bg = BlueGreenDeployer()
        dep = bg.deploy("v1.0")
        self.assertEqual(dep.state, DeploymentState.LIVE)
        self.assertEqual(dep.version, "v1.0")
        self.assertEqual(bg.active_slot, SlotColor.GREEN)
        self.assertEqual(len(bg.history), 1)

    def test_deploy_switches_slot_alternately(self) -> None:
        bg = BlueGreenDeployer()
        bg.deploy("v1")
        self.assertEqual(bg.active_slot, SlotColor.GREEN)
        bg.deploy("v2")
        self.assertEqual(bg.active_slot, SlotColor.BLUE)

    def test_deploy_fn_returns_false(self) -> None:
        bg = BlueGreenDeployer(deploy_fn=lambda _s, _v: False)
        dep = bg.deploy("v1")
        self.assertEqual(dep.state, DeploymentState.FAILED)
        self.assertEqual(bg.active_slot, SlotColor.BLUE)

    def test_deploy_fn_raises(self) -> None:
        def bad_deploy(_s, _v):
            raise RuntimeError("boom")

        bg = BlueGreenDeployer(deploy_fn=bad_deploy)
        dep = bg.deploy("v1")
        self.assertEqual(dep.state, DeploymentState.FAILED)
        self.assertIn("boom", dep.error)

    def test_health_check_fails(self) -> None:
        bg = BlueGreenDeployer(
            health_check=lambda _s: HealthCheckResult(healthy=False),
            health_retries=1,
            health_interval_s=0,
        )
        dep = bg.deploy("v1")
        self.assertEqual(dep.state, DeploymentState.FAILED)
        self.assertIn("Health", dep.error)

    def test_switch_fn_fails(self) -> None:
        bg = BlueGreenDeployer(switch_fn=lambda _s: False)
        dep = bg.deploy("v1")
        self.assertEqual(dep.state, DeploymentState.FAILED)

    def test_switch_fn_raises(self) -> None:
        def bad_switch(_s):
            raise RuntimeError("switch error")

        bg = BlueGreenDeployer(switch_fn=bad_switch)
        dep = bg.deploy("v1")
        self.assertEqual(dep.state, DeploymentState.FAILED)
        self.assertIn("switch error", dep.error)

    def test_rollback(self) -> None:
        bg = BlueGreenDeployer()
        bg.deploy("v1")
        self.assertEqual(bg.active_slot, SlotColor.GREEN)
        dep = bg.rollback()
        self.assertEqual(dep.state, DeploymentState.LIVE)
        self.assertEqual(bg.active_slot, SlotColor.BLUE)

    def test_rollback_switch_fails(self) -> None:
        call_count = 0

        def switch_fn(_s):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                return False
            return True

        bg = BlueGreenDeployer(switch_fn=switch_fn)
        bg.deploy("v1")
        dep = bg.rollback()
        self.assertEqual(dep.state, DeploymentState.FAILED)

    def test_status(self) -> None:
        bg = BlueGreenDeployer()
        s = bg.status()
        self.assertEqual(s["active_slot"], "blue")
        self.assertEqual(s["deployments"], 0)
        bg.deploy("v1")
        s = bg.status()
        self.assertEqual(s["deployments"], 1)

    def test_slots_property(self) -> None:
        bg = BlueGreenDeployer()
        slots = bg.slots
        self.assertIn(SlotColor.BLUE, slots)
        self.assertIn(SlotColor.GREEN, slots)

    def test_deploy_logs(self) -> None:
        bg = BlueGreenDeployer()
        dep = bg.deploy("v1")
        self.assertTrue(len(dep.logs) > 0)
        self.assertTrue(any("v1" in log for log in dep.logs))

    def test_health_retries(self) -> None:
        attempts = []

        def health_fn(_s):
            attempts.append(1)
            return HealthCheckResult(healthy=len(attempts) >= 3)

        bg = BlueGreenDeployer(health_check=health_fn, health_retries=3, health_interval_s=0)
        dep = bg.deploy("v1")
        self.assertEqual(dep.state, DeploymentState.LIVE)
        self.assertEqual(len(attempts), 3)


if __name__ == "__main__":
    unittest.main()
