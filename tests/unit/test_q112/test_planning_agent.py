"""Tests for TodoPlanningAgent — Task 693."""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

from lidco.tasks.planning_agent import TodoPlan, TodoPlanningAgent
from lidco.tasks.live_todo import TodoItem, TodoStatus


class TestTodoPlan(unittest.TestCase):
    def test_creation(self):
        plan = TodoPlan(id="p1", description="Build feature", items=[])
        self.assertEqual(plan.id, "p1")
        self.assertEqual(plan.description, "Build feature")
        self.assertEqual(plan.items, [])

    def test_to_dag_empty(self):
        plan = TodoPlan(id="p1", description="empty", items=[])
        result = plan.to_dag()
        self.assertEqual(result, {})

    def test_to_dag_single(self):
        items = [TodoItem(id="t1", label="Step 1")]
        plan = TodoPlan(id="p1", description="one step", items=items)
        dag = plan.to_dag()
        self.assertIn("t1", dag)
        self.assertEqual(dag["t1"].label, "Step 1")

    def test_to_dag_with_deps(self):
        items = [
            TodoItem(id="t1", label="First"),
            TodoItem(id="t2", label="Second", depends_on=["t1"]),
        ]
        plan = TodoPlan(id="p1", description="two steps", items=items)
        dag = plan.to_dag()
        self.assertIn("t1", dag)
        self.assertIn("t2", dag)
        self.assertEqual(dag["t2"].depends_on, ["t1"])

    def test_to_dag_preserves_order(self):
        items = [
            TodoItem(id="a", label="A"),
            TodoItem(id="b", label="B", depends_on=["a"]),
            TodoItem(id="c", label="C", depends_on=["b"]),
        ]
        plan = TodoPlan(id="p1", description="chain", items=items)
        dag = plan.to_dag()
        self.assertEqual(list(dag.keys()), ["a", "b", "c"])

    def test_items_are_stored(self):
        items = [TodoItem(id="1", label="X")]
        plan = TodoPlan(id="p1", description="test", items=items)
        self.assertEqual(len(plan.items), 1)


class TestTodoPlanningAgent(unittest.TestCase):
    def test_plan_simple_prompt(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("Build a REST API")
        self.assertIsInstance(plan, TodoPlan)
        self.assertTrue(len(plan.items) > 0)

    def test_plan_generates_id(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("Do something")
        self.assertTrue(plan.id)

    def test_plan_description_matches_prompt(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("Build a cache system")
        self.assertEqual(plan.description, "Build a cache system")

    def test_plan_numbered_steps(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("1. Research\n2. Design\n3. Implement\n4. Test")
        self.assertEqual(len(plan.items), 4)
        self.assertIn("Research", plan.items[0].label)

    def test_plan_newline_steps(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("Setup env\nWrite code\nRun tests")
        self.assertEqual(len(plan.items), 3)

    def test_plan_generic_fallback(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("Build something cool")
        # single line, no numbers => 3 generic steps
        self.assertEqual(len(plan.items), 3)

    def test_plan_items_have_ids(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("1. A\n2. B")
        for item in plan.items:
            self.assertTrue(item.id)

    def test_plan_items_status_pending(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("1. A\n2. B")
        for item in plan.items:
            self.assertEqual(item.status, TodoStatus.PENDING)

    def test_plan_with_llm_fn(self):
        response = json.dumps({
            "items": [
                {"id": "s1", "label": "Research options"},
                {"id": "s2", "label": "Implement solution", "depends_on": ["s1"]},
            ]
        })
        llm_fn = MagicMock(return_value=response)
        agent = TodoPlanningAgent()
        plan = agent.plan("Build feature", llm_fn=llm_fn)
        llm_fn.assert_called_once()
        self.assertEqual(len(plan.items), 2)
        self.assertEqual(plan.items[1].depends_on, ["s1"])

    def test_plan_with_llm_fn_invalid_json_falls_back(self):
        llm_fn = MagicMock(return_value="not json at all")
        agent = TodoPlanningAgent()
        plan = agent.plan("Build feature", llm_fn=llm_fn)
        # Falls back to heuristic
        self.assertTrue(len(plan.items) > 0)

    def test_plan_empty_prompt(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("")
        # Should still return a plan with generic steps
        self.assertIsInstance(plan, TodoPlan)

    def test_plan_whitespace_prompt(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("   \n  \n  ")
        self.assertIsInstance(plan, TodoPlan)

    def test_estimate_effort(self):
        agent = TodoPlanningAgent()
        items = [
            TodoItem(id="1", label="Research API docs"),
            TodoItem(id="2", label="Implement complex parser"),
            TodoItem(id="3", label="Write unit tests"),
        ]
        plan = TodoPlan(id="p1", description="test", items=items)
        effort = agent.estimate_effort(plan)
        self.assertIn("1", effort)
        self.assertIn("2", effort)
        self.assertIn("3", effort)
        for v in effort.values():
            self.assertIn(v, ("low", "medium", "high"))

    def test_estimate_effort_empty_plan(self):
        agent = TodoPlanningAgent()
        plan = TodoPlan(id="p1", description="empty", items=[])
        effort = agent.estimate_effort(plan)
        self.assertEqual(effort, {})

    def test_estimate_effort_keywords(self):
        agent = TodoPlanningAgent()
        items = [
            TodoItem(id="1", label="refactor the entire architecture"),
            TodoItem(id="2", label="fix typo"),
        ]
        plan = TodoPlan(id="p1", description="test", items=items)
        effort = agent.estimate_effort(plan)
        self.assertEqual(effort["1"], "high")
        self.assertEqual(effort["2"], "low")

    def test_event_bus_fires_on_plan(self):
        bus = MagicMock()
        agent = TodoPlanningAgent(event_bus=bus)
        agent.plan("Do something")
        bus.publish.assert_called()
        call_types = [c[0][0] for c in bus.publish.call_args_list]
        self.assertIn("plan.created", call_types)

    def test_event_bus_not_required(self):
        agent = TodoPlanningAgent(event_bus=None)
        plan = agent.plan("Do something")
        self.assertIsInstance(plan, TodoPlan)

    def test_plan_numbered_with_dots(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("1. First step\n2. Second step")
        self.assertEqual(len(plan.items), 2)

    def test_plan_numbered_with_parentheses(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("1) Alpha\n2) Beta\n3) Gamma")
        self.assertEqual(len(plan.items), 3)

    def test_plan_mixed_content_stripped(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("  Setup  \n  Build  \n  Deploy  ")
        for item in plan.items:
            self.assertEqual(item.label, item.label.strip())

    def test_plan_single_line_no_numbers(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("Just do it all")
        # no newlines, no numbers => generic 3 steps
        self.assertEqual(len(plan.items), 3)

    def test_plan_llm_fn_with_missing_items_key(self):
        llm_fn = MagicMock(return_value=json.dumps({"steps": []}))
        agent = TodoPlanningAgent()
        plan = agent.plan("Build feature", llm_fn=llm_fn)
        # missing "items" key => fallback to heuristic
        self.assertTrue(len(plan.items) > 0)

    def test_plan_to_dag_roundtrip(self):
        agent = TodoPlanningAgent()
        plan = agent.plan("1. Research\n2. Implement\n3. Test")
        dag = plan.to_dag()
        self.assertEqual(len(dag), 3)


if __name__ == "__main__":
    unittest.main()
