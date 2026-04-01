"""Tests for UltraPlanner (Q238)."""
from __future__ import annotations

import unittest

from lidco.modes.ultra_planner import (
    PlanPhase,
    PlanSection,
    UltraPlan,
    UltraPlanner,
)


class TestPlanPhase(unittest.TestCase):
    def test_values(self):
        self.assertEqual(PlanPhase.GATHER.value, "gather")
        self.assertEqual(PlanPhase.FINALIZE.value, "finalize")

    def test_all_phases(self):
        self.assertEqual(len(PlanPhase), 5)


class TestPlanSection(unittest.TestCase):
    def test_frozen(self):
        sec = PlanSection(title="T", content="C")
        with self.assertRaises(AttributeError):
            sec.title = "X"  # type: ignore[misc]

    def test_defaults(self):
        sec = PlanSection(title="T", content="C")
        self.assertEqual(sec.phase, PlanPhase.PLAN)
        self.assertEqual(sec.confidence, 0.5)


class TestUltraPlan(unittest.TestCase):
    def test_frozen(self):
        plan = UltraPlan(title="P")
        with self.assertRaises(AttributeError):
            plan.title = "X"  # type: ignore[misc]

    def test_defaults(self):
        plan = UltraPlan(title="P")
        self.assertEqual(plan.sections, ())
        self.assertEqual(plan.risks, ())
        self.assertEqual(plan.checklist, ())
        self.assertEqual(plan.passes, 0)


class TestUltraPlanner(unittest.TestCase):
    def setUp(self):
        self.planner = UltraPlanner(max_passes=3)

    def test_create_plan(self):
        plan = self.planner.create_plan("My Plan", "Build a widget")
        self.assertEqual(plan.title, "My Plan")
        self.assertEqual(len(plan.sections), 2)
        self.assertEqual(plan.passes, 1)

    def test_create_plan_empty_desc(self):
        plan = self.planner.create_plan("Empty", "")
        self.assertEqual(len(plan.sections), 0)

    def test_add_section(self):
        plan = self.planner.create_plan("P", "desc")
        updated = self.planner.add_section(plan, "Testing", "Write tests")
        self.assertEqual(len(updated.sections), len(plan.sections) + 1)
        self.assertEqual(updated.sections[-1].title, "Testing")
        # Original unchanged
        self.assertEqual(len(plan.sections), 2)

    def test_critique_finds_issues(self):
        plan = self.planner.create_plan("P", "Build it")
        issues = self.planner.critique(plan)
        self.assertIsInstance(issues, list)
        self.assertTrue(len(issues) > 0)
        # Missing testing plan
        self.assertTrue(any("test" in i.lower() for i in issues))

    def test_critique_short_content(self):
        plan = UltraPlan(title="P", sections=(PlanSection("S", "x"),))
        issues = self.planner.critique(plan)
        self.assertTrue(any("short" in i.lower() for i in issues))

    def test_revise_increments_passes(self):
        plan = self.planner.create_plan("P", "desc")
        revised = self.planner.revise(plan, ["Fix this"])
        self.assertEqual(revised.passes, plan.passes + 1)
        self.assertIn("Fix this", revised.risks)

    def test_add_risk(self):
        plan = self.planner.create_plan("P", "d")
        updated = self.planner.add_risk(plan, "Data loss")
        self.assertIn("Data loss", updated.risks)
        self.assertNotIn("Data loss", plan.risks)

    def test_add_checklist_item(self):
        plan = self.planner.create_plan("P", "d")
        updated = self.planner.add_checklist_item(plan, "Deploy")
        self.assertIn("Deploy", updated.checklist)

    def test_to_markdown(self):
        plan = self.planner.create_plan("My Plan", "Description here is long enough")
        plan = self.planner.add_risk(plan, "Risk 1")
        plan = self.planner.add_checklist_item(plan, "Item 1")
        md = self.planner.to_markdown(plan)
        self.assertIn("# My Plan", md)
        self.assertIn("## Risks", md)
        self.assertIn("- Risk 1", md)
        self.assertIn("- [ ] Item 1", md)

    def test_summary(self):
        plan = self.planner.create_plan("P", "d")
        s = self.planner.summary(plan)
        self.assertIn("P", s)
        self.assertIn("sections", s)
        self.assertIn("pass", s)


if __name__ == "__main__":
    unittest.main()
