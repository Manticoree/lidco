"""Tests for lidco.incident.recovery."""
from __future__ import annotations

import unittest

from lidco.incident.recovery import RecoveryAction, RecoveryManager, RecoveryPlan


class TestRecoveryAction(unittest.TestCase):
    def test_frozen(self) -> None:
        ra = RecoveryAction(id="a1", incident_id="i1", action="revert", target="db")
        with self.assertRaises(AttributeError):
            ra.action = "x"  # type: ignore[misc]

    def test_default_status(self) -> None:
        ra = RecoveryAction(id="a1", incident_id="i1", action="revert", target="db")
        self.assertEqual(ra.status, "pending")


class TestRecoveryPlan(unittest.TestCase):
    def test_mutable(self) -> None:
        plan = RecoveryPlan(incident_id="i1")
        plan.status = "approved"
        self.assertEqual(plan.status, "approved")

    def test_default_values(self) -> None:
        plan = RecoveryPlan(incident_id="i1")
        self.assertEqual(plan.actions, [])
        self.assertEqual(plan.status, "draft")


class TestRecoveryManager(unittest.TestCase):
    def setUp(self) -> None:
        self.rm = RecoveryManager()

    def test_create_plan(self) -> None:
        plan = self.rm.create_plan("inc1")
        self.assertEqual(plan.incident_id, "inc1")
        self.assertEqual(plan.status, "draft")

    def test_add_action(self) -> None:
        self.rm.create_plan("inc1")
        ra = self.rm.add_action("inc1", "revert", "database")
        self.assertEqual(ra.action, "revert")
        self.assertEqual(ra.target, "database")
        plan = self.rm.get_plan("inc1")
        self.assertEqual(len(plan.actions), 1)

    def test_add_action_auto_creates_plan(self) -> None:
        ra = self.rm.add_action("inc2", "rotate", "keys")
        self.assertIsNotNone(self.rm.get_plan("inc2"))

    def test_execute_plan(self) -> None:
        self.rm.create_plan("inc1")
        self.rm.add_action("inc1", "revert", "db")
        self.rm.add_action("inc1", "rotate", "keys")
        plan = self.rm.execute_plan("inc1")
        self.assertEqual(plan.status, "completed")
        for a in plan.actions:
            self.assertEqual(a.status, "completed")

    def test_execute_empty_plan(self) -> None:
        plan = self.rm.execute_plan("inc_new")
        self.assertEqual(plan.status, "completed")
        self.assertEqual(len(plan.actions), 0)

    def test_get_plan_none(self) -> None:
        self.assertIsNone(self.rm.get_plan("nonexistent"))

    def test_generate_report(self) -> None:
        self.rm.create_plan("inc1")
        self.rm.add_action("inc1", "revert", "db")
        report = self.rm.generate_report("inc1")
        self.assertIn("inc1", report)
        self.assertIn("revert", report)

    def test_generate_report_no_plan(self) -> None:
        report = self.rm.generate_report("missing")
        self.assertIn("No recovery plan", report)

    def test_all_plans(self) -> None:
        self.rm.create_plan("a")
        self.rm.create_plan("b")
        self.assertEqual(len(self.rm.all_plans()), 2)

    def test_summary(self) -> None:
        self.rm.create_plan("inc1")
        self.rm.add_action("inc1", "revert", "db")
        s = self.rm.summary()
        self.assertEqual(s["total_plans"], 1)
        self.assertEqual(s["total_actions"], 1)


if __name__ == "__main__":
    unittest.main()
