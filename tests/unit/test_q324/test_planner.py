"""Tests for lidco.dr.planner — RecoveryPlanner."""

from __future__ import annotations

import unittest

from lidco.dr.planner import (
    Component,
    ComponentTier,
    DRPlan,
    PlanStatus,
    RecoveryPlanner,
    RunbookStep,
)


class TestComponent(unittest.TestCase):
    def test_valid_component(self) -> None:
        c = Component(name="db", tier=ComponentTier.CRITICAL)
        self.assertEqual(c.name, "db")
        self.assertEqual(c.rto_seconds, 3600)
        self.assertEqual(c.rpo_seconds, 900)

    def test_empty_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            Component(name="", tier=ComponentTier.LOW)

    def test_negative_rto_raises(self) -> None:
        with self.assertRaises(ValueError):
            Component(name="x", tier=ComponentTier.LOW, rto_seconds=-1)

    def test_negative_rpo_raises(self) -> None:
        with self.assertRaises(ValueError):
            Component(name="x", tier=ComponentTier.LOW, rpo_seconds=-1)


class TestRunbookStep(unittest.TestCase):
    def test_valid_step(self) -> None:
        s = RunbookStep(order=0, description="Do something", component="db")
        self.assertEqual(s.order, 0)

    def test_negative_order_raises(self) -> None:
        with self.assertRaises(ValueError):
            RunbookStep(order=-1, description="x", component="db")

    def test_empty_description_raises(self) -> None:
        with self.assertRaises(ValueError):
            RunbookStep(order=0, description="", component="db")


class TestDRPlan(unittest.TestCase):
    def test_total_estimated_seconds(self) -> None:
        plan = DRPlan(
            plan_id="p1",
            name="Test",
            status=PlanStatus.DRAFT,
            runbook=[
                RunbookStep(order=0, description="A", component="db", estimated_seconds=100),
                RunbookStep(order=1, description="B", component="app", estimated_seconds=200),
            ],
            target_rto_seconds=500,
        )
        self.assertEqual(plan.total_estimated_seconds, 300)
        self.assertTrue(plan.meets_rto)

    def test_exceeds_rto(self) -> None:
        plan = DRPlan(
            plan_id="p2",
            name="Over",
            status=PlanStatus.DRAFT,
            runbook=[
                RunbookStep(order=0, description="A", component="db", estimated_seconds=600),
            ],
            target_rto_seconds=500,
        )
        self.assertFalse(plan.meets_rto)

    def test_to_dict(self) -> None:
        plan = DRPlan(
            plan_id="p3",
            name="Dict Test",
            status=PlanStatus.VALIDATED,
            components=[Component(name="db", tier=ComponentTier.CRITICAL)],
        )
        d = plan.to_dict()
        self.assertEqual(d["plan_id"], "p3")
        self.assertEqual(d["status"], "validated")
        self.assertEqual(len(d["components"]), 1)


class TestRecoveryPlanner(unittest.TestCase):
    def _planner_with_components(self) -> RecoveryPlanner:
        p = RecoveryPlanner()
        p.add_component(Component(
            name="database",
            tier=ComponentTier.CRITICAL,
            rto_seconds=600,
            recovery_steps=["Stop writes", "Restore backup"],
        ))
        p.add_component(Component(
            name="cache",
            tier=ComponentTier.MEDIUM,
            rto_seconds=120,
            dependencies=["database"],
            recovery_steps=["Flush cache", "Warm up"],
        ))
        p.add_component(Component(
            name="app",
            tier=ComponentTier.HIGH,
            rto_seconds=300,
            dependencies=["database", "cache"],
            recovery_steps=["Redeploy"],
        ))
        return p

    def test_add_and_list_components(self) -> None:
        p = self._planner_with_components()
        self.assertEqual(len(p.components), 3)
        self.assertIn("database", p.components)

    def test_remove_component(self) -> None:
        p = self._planner_with_components()
        self.assertTrue(p.remove_component("cache"))
        self.assertEqual(len(p.components), 2)
        self.assertFalse(p.remove_component("nonexistent"))

    def test_generate_plan(self) -> None:
        p = self._planner_with_components()
        plan = p.generate_plan("Test Plan", target_rto=3600)
        self.assertEqual(plan.name, "Test Plan")
        self.assertEqual(plan.status, PlanStatus.DRAFT)
        self.assertEqual(len(plan.components), 3)
        self.assertGreater(len(plan.runbook), 0)

    def test_dependency_ordering(self) -> None:
        p = self._planner_with_components()
        plan = p.generate_plan("Order Test")
        # database should appear before app in the runbook
        db_idx = next(i for i, s in enumerate(plan.runbook) if s.component == "database")
        app_idx = next(i for i, s in enumerate(plan.runbook) if s.component == "app")
        self.assertLess(db_idx, app_idx)

    def test_validate_plan_success(self) -> None:
        p = self._planner_with_components()
        plan = p.generate_plan("Valid", target_rto=36000)
        issues = p.validate_plan(plan.plan_id)
        self.assertEqual(issues, [])
        refreshed = p.get_plan(plan.plan_id)
        self.assertEqual(refreshed.status, PlanStatus.VALIDATED)

    def test_validate_plan_exceeds_rto(self) -> None:
        p = self._planner_with_components()
        plan = p.generate_plan("Tight", target_rto=1)
        issues = p.validate_plan(plan.plan_id)
        self.assertTrue(any("exceeds RTO" in i for i in issues))

    def test_validate_nonexistent(self) -> None:
        p = RecoveryPlanner()
        issues = p.validate_plan("nope")
        self.assertEqual(len(issues), 1)
        self.assertIn("not found", issues[0])

    def test_validate_empty_plan(self) -> None:
        p = RecoveryPlanner()
        plan = p.generate_plan("Empty")
        issues = p.validate_plan(plan.plan_id)
        self.assertTrue(any("no components" in i for i in issues))

    def test_activate_plan(self) -> None:
        p = self._planner_with_components()
        plan = p.generate_plan("Activate", target_rto=36000)
        p.validate_plan(plan.plan_id)
        self.assertTrue(p.activate_plan(plan.plan_id))
        self.assertEqual(p.get_plan(plan.plan_id).status, PlanStatus.ACTIVE)

    def test_activate_draft_fails(self) -> None:
        p = self._planner_with_components()
        plan = p.generate_plan("Draft")
        self.assertFalse(p.activate_plan(plan.plan_id))

    def test_activate_nonexistent(self) -> None:
        p = RecoveryPlanner()
        self.assertFalse(p.activate_plan("nope"))

    def test_list_plans(self) -> None:
        p = self._planner_with_components()
        p.generate_plan("One")
        p.generate_plan("Two")
        self.assertEqual(len(p.list_plans()), 2)

    def test_cycle_detection(self) -> None:
        p = RecoveryPlanner()
        p.add_component(Component(name="a", tier=ComponentTier.LOW, dependencies=["b"]))
        p.add_component(Component(name="b", tier=ComponentTier.LOW, dependencies=["a"]))
        plan = p.generate_plan("Cycle")
        issues = p.validate_plan(plan.plan_id)
        self.assertTrue(any("Circular" in i for i in issues))

    def test_unknown_dependency(self) -> None:
        p = RecoveryPlanner()
        p.add_component(Component(name="x", tier=ComponentTier.LOW, dependencies=["missing"]))
        plan = p.generate_plan("Missing dep")
        issues = p.validate_plan(plan.plan_id)
        self.assertTrue(any("unknown" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
