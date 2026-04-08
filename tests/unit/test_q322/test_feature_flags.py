"""Tests for lidco.deploy.feature_flags — FeatureFlagDeployer."""

from __future__ import annotations

import unittest

from lidco.deploy.feature_flags import (
    ExperimentResult,
    FeatureFlag,
    FeatureFlagDeployer,
    FlagState,
    RolloutPhase,
    RolloutPlan,
)


class TestFlagState(unittest.TestCase):
    def test_values(self) -> None:
        self.assertIn("killed", [s.value for s in FlagState])
        self.assertIn("gradual", [s.value for s in FlagState])


class TestRolloutPhase(unittest.TestCase):
    def test_values(self) -> None:
        self.assertIn("rolling_out", [p.value for p in RolloutPhase])
        self.assertIn("stable", [p.value for p in RolloutPhase])


class TestFeatureFlag(unittest.TestCase):
    def test_auto_id(self) -> None:
        f = FeatureFlag(name="test")
        self.assertTrue(len(f.flag_id) > 0)

    def test_defaults(self) -> None:
        f = FeatureFlag(name="x")
        self.assertEqual(f.state, FlagState.DISABLED)
        self.assertEqual(f.rollout_pct, 0.0)
        self.assertEqual(f.target_users, [])


class TestRolloutPlan(unittest.TestCase):
    def test_auto_id(self) -> None:
        p = RolloutPlan()
        self.assertTrue(len(p.plan_id) > 0)

    def test_progress_empty(self) -> None:
        p = RolloutPlan(steps=[])
        self.assertEqual(p.progress_pct, 0.0)

    def test_progress_mid(self) -> None:
        p = RolloutPlan(steps=[10.0, 50.0, 100.0], current_step=2)
        self.assertAlmostEqual(p.progress_pct, 50.0)

    def test_progress_complete(self) -> None:
        p = RolloutPlan(steps=[10.0, 100.0], current_step=5)
        self.assertAlmostEqual(p.progress_pct, 100.0)


class TestExperimentResult(unittest.TestCase):
    def test_rates(self) -> None:
        e = ExperimentResult(
            control_count=100, treatment_count=100,
            control_success=50, treatment_success=60,
        )
        self.assertAlmostEqual(e.control_rate, 0.5)
        self.assertAlmostEqual(e.treatment_rate, 0.6)
        self.assertAlmostEqual(e.lift, 0.2)

    def test_zero_control(self) -> None:
        e = ExperimentResult()
        self.assertEqual(e.control_rate, 0.0)
        self.assertEqual(e.lift, 0.0)


class TestFeatureFlagDeployer(unittest.TestCase):
    def test_create_flag(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("dark-mode", description="Toggle dark mode")
        self.assertEqual(f.name, "dark-mode")
        self.assertEqual(f.state, FlagState.DISABLED)

    def test_get_flag(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        self.assertEqual(fd.get_flag(f.flag_id).name, "x")
        self.assertIsNone(fd.get_flag("nonexistent"))

    def test_list_flags(self) -> None:
        fd = FeatureFlagDeployer()
        fd.create_flag("a")
        fd.create_flag("b")
        self.assertEqual(len(fd.list_flags()), 2)

    def test_delete_flag(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        self.assertTrue(fd.delete_flag(f.flag_id))
        self.assertFalse(fd.delete_flag("nonexistent"))
        self.assertEqual(len(fd.list_flags()), 0)

    def test_is_enabled_disabled(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        self.assertFalse(fd.is_enabled(f.flag_id, user_id="u1"))

    def test_is_enabled_enabled(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        fd.enable(f.flag_id)
        self.assertTrue(fd.is_enabled(f.flag_id, user_id="u1"))

    def test_is_enabled_killed(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        fd.enable(f.flag_id)
        fd.kill(f.flag_id)
        self.assertFalse(fd.is_enabled(f.flag_id, user_id="u1"))

    def test_is_enabled_nonexistent(self) -> None:
        fd = FeatureFlagDeployer()
        self.assertFalse(fd.is_enabled("nope"))

    def test_targeted_users(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        fd.set_targets(f.flag_id, users=["alice", "bob"])
        self.assertTrue(fd.is_enabled(f.flag_id, user_id="alice"))
        self.assertFalse(fd.is_enabled(f.flag_id, user_id="charlie"))

    def test_targeted_groups(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        fd.set_targets(f.flag_id, groups=["beta"])
        self.assertTrue(fd.is_enabled(f.flag_id, user_id="u1", groups=["beta"]))
        self.assertFalse(fd.is_enabled(f.flag_id, user_id="u1", groups=["stable"]))

    def test_exclude_users(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        fd.enable(f.flag_id)
        fd.set_targets(f.flag_id, exclude=["blocked"])
        # After set_targets with no users/groups, state becomes TARGETED
        # Re-enable to test exclude on ENABLED state
        fd.enable(f.flag_id)
        # We need to set exclude directly
        flag = fd.get_flag(f.flag_id)
        fd._flags[f.flag_id] = FeatureFlag(
            flag_id=f.flag_id, name="x",
            state=FlagState.ENABLED,
            exclude_users=["blocked"],
        )
        self.assertFalse(fd.is_enabled(f.flag_id, user_id="blocked"))
        self.assertTrue(fd.is_enabled(f.flag_id, user_id="allowed"))

    def test_gradual_rollout(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        plan = fd.start_rollout(f.flag_id, steps=[50.0, 100.0])
        self.assertIsNotNone(plan)
        self.assertEqual(plan.phase, RolloutPhase.ROLLING_OUT)
        flag = fd.get_flag(f.flag_id)
        self.assertEqual(flag.state, FlagState.GRADUAL)
        self.assertAlmostEqual(flag.rollout_pct, 50.0)

    def test_advance_rollout(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        fd.start_rollout(f.flag_id, steps=[25.0, 100.0])
        plan = fd.advance_rollout(f.flag_id)
        # Second step = 100%
        flag = fd.get_flag(f.flag_id)
        self.assertEqual(flag.state, FlagState.ENABLED)
        self.assertEqual(plan.phase, RolloutPhase.STABLE)

    def test_start_rollout_nonexistent(self) -> None:
        fd = FeatureFlagDeployer()
        self.assertIsNone(fd.start_rollout("nope"))

    def test_kill_switch(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        fd.enable(f.flag_id)
        self.assertTrue(fd.kill(f.flag_id))
        self.assertFalse(fd.is_enabled(f.flag_id))

    def test_kill_nonexistent(self) -> None:
        fd = FeatureFlagDeployer()
        self.assertFalse(fd.kill("nope"))

    def test_enable_nonexistent(self) -> None:
        fd = FeatureFlagDeployer()
        self.assertFalse(fd.enable("nope"))

    def test_set_targets_nonexistent(self) -> None:
        fd = FeatureFlagDeployer()
        self.assertIsNone(fd.set_targets("nope", users=["a"]))

    def test_register_group(self) -> None:
        fd = FeatureFlagDeployer()
        fd.register_group("beta", ["u1", "u2"])
        self.assertEqual(fd._user_groups["beta"], ["u1", "u2"])

    def test_record_experiment(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        fd.enable(f.flag_id)
        result = fd.record_experiment(f.flag_id, "u1", success=True)
        self.assertIsNotNone(result)
        self.assertEqual(result.treatment_count, 1)
        self.assertEqual(result.treatment_success, 1)

    def test_record_experiment_control(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        # flag is disabled so user is in control
        result = fd.record_experiment(f.flag_id, "u1", success=True)
        self.assertEqual(result.control_count, 1)

    def test_record_experiment_nonexistent(self) -> None:
        fd = FeatureFlagDeployer()
        self.assertIsNone(fd.record_experiment("nope", "u1", True))

    def test_get_experiment(self) -> None:
        fd = FeatureFlagDeployer()
        f = fd.create_flag("x")
        fd.record_experiment(f.flag_id, "u1", True)
        exp = fd.get_experiment(f.flag_id)
        self.assertIsNotNone(exp)

    def test_status(self) -> None:
        fd = FeatureFlagDeployer()
        fd.create_flag("a")
        f2 = fd.create_flag("b")
        fd.enable(f2.flag_id)
        s = fd.status()
        self.assertEqual(s["total_flags"], 2)
        self.assertEqual(s["enabled"], 1)

    def test_hash_bucket_deterministic(self) -> None:
        b1 = FeatureFlagDeployer._hash_bucket("flag1", "user1")
        b2 = FeatureFlagDeployer._hash_bucket("flag1", "user1")
        self.assertEqual(b1, b2)

    def test_hash_bucket_range(self) -> None:
        b = FeatureFlagDeployer._hash_bucket("f", "u")
        self.assertGreaterEqual(b, 0.0)
        self.assertLessEqual(b, 100.0)


if __name__ == "__main__":
    unittest.main()
