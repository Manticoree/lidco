"""Tests for UpdatePlanner (Q255)."""
from __future__ import annotations

import unittest

from lidco.depgraph.update_planner import UpdatePlan, UpdatePlanner


class TestUpdatePlan(unittest.TestCase):
    def test_frozen(self):
        plan = UpdatePlan(package="a", current="1.0", target="2.0", risk="high")
        with self.assertRaises(AttributeError):
            plan.package = "b"  # type: ignore[misc]

    def test_defaults(self):
        plan = UpdatePlan(package="a", current="1.0", target="1.1", risk="low")
        self.assertFalse(plan.breaking)

    def test_fields(self):
        plan = UpdatePlan(package="x", current="1.0", target="3.0", risk="high", breaking=True)
        self.assertEqual(plan.package, "x")
        self.assertTrue(plan.breaking)


class TestUpdatePlanner(unittest.TestCase):
    def setUp(self):
        self.planner = UpdatePlanner()

    def test_risk_score_low(self):
        self.assertEqual(self.planner.risk_score("pkg", "1.0.0", "1.5.0"), "low")

    def test_risk_score_medium(self):
        self.assertEqual(self.planner.risk_score("pkg", "1.0.0", "2.0.0"), "medium")

    def test_risk_score_high(self):
        self.assertEqual(self.planner.risk_score("pkg", "1.0.0", "5.0.0"), "high")

    def test_plan_single(self):
        plans = self.planner.plan([
            {"package": "a", "current": "1.0.0", "target": "1.1.0"},
        ])
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].package, "a")
        self.assertEqual(plans[0].risk, "low")
        self.assertFalse(plans[0].breaking)

    def test_plan_breaking(self):
        plans = self.planner.plan([
            {"package": "b", "current": "1.0.0", "target": "2.0.0"},
        ])
        self.assertTrue(plans[0].breaking)

    def test_plan_multiple(self):
        plans = self.planner.plan([
            {"package": "a", "current": "1.0", "target": "1.1"},
            {"package": "b", "current": "1.0", "target": "5.0"},
        ])
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[1].risk, "high")

    def test_rollback_plan(self):
        plans = self.planner.plan([
            {"package": "a", "current": "1.0", "target": "2.0"},
        ])
        rollbacks = self.planner.rollback_plan(plans)
        self.assertEqual(len(rollbacks), 1)
        self.assertEqual(rollbacks[0]["package"], "a")
        self.assertEqual(rollbacks[0]["from"], "2.0")
        self.assertEqual(rollbacks[0]["to"], "1.0")

    def test_rollback_empty(self):
        self.assertEqual(self.planner.rollback_plan([]), [])

    def test_summary_empty(self):
        self.assertEqual(self.planner.summary([]), "No updates planned.")

    def test_summary_with_plans(self):
        plans = self.planner.plan([
            {"package": "a", "current": "1.0", "target": "1.1"},
            {"package": "b", "current": "1.0", "target": "3.0"},
        ])
        s = self.planner.summary(plans)
        self.assertIn("2 update(s)", s)
        self.assertIn("1 breaking", s)
        self.assertIn("[BREAKING]", s)
        self.assertIn("a 1.0 -> 1.1", s)

    def test_summary_no_breaking(self):
        plans = self.planner.plan([
            {"package": "a", "current": "1.0", "target": "1.1"},
        ])
        s = self.planner.summary(plans)
        self.assertIn("0 breaking", s)
        self.assertNotIn("[BREAKING]", s)


if __name__ == "__main__":
    unittest.main()
