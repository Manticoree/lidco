"""Tests for lidco.goals.subtasks."""
from __future__ import annotations

import unittest

from lidco.goals.parser import Goal
from lidco.goals.subtasks import Subtask, SubtaskGenerator


class TestSubtaskGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = SubtaskGenerator()

    def test_generate_no_criteria(self):
        goal = Goal(name="Simple goal")
        subtasks = self.gen.generate(goal)
        self.assertEqual(len(subtasks), 1)
        self.assertEqual(subtasks[0].description, "Simple goal")
        self.assertEqual(subtasks[0].depends_on, [])

    def test_generate_with_criteria(self):
        goal = Goal(name="Auth", acceptance_criteria=["Login works", "Logout works", "Session persists"])
        subtasks = self.gen.generate(goal)
        self.assertEqual(len(subtasks), 3)

    def test_generate_linear_deps(self):
        goal = Goal(name="X", acceptance_criteria=["A", "B", "C"])
        subtasks = self.gen.generate(goal)
        self.assertEqual(subtasks[0].depends_on, [])
        self.assertEqual(subtasks[1].depends_on, [subtasks[0].id])
        self.assertEqual(subtasks[2].depends_on, [subtasks[1].id])

    def test_subtask_ids_unique(self):
        goal = Goal(name="X", acceptance_criteria=["A", "B", "C"])
        subtasks = self.gen.generate(goal)
        ids = [s.id for s in subtasks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_subtask_id_prefix(self):
        goal = Goal(name="Test")
        subtasks = self.gen.generate(goal)
        self.assertTrue(subtasks[0].id.startswith("st-"))

    def test_dependency_graph(self):
        goal = Goal(name="X", acceptance_criteria=["A", "B"])
        subtasks = self.gen.generate(goal)
        graph = self.gen.dependency_graph(subtasks)
        self.assertIn(subtasks[0].id, graph)
        self.assertIn(subtasks[1].id, graph)
        self.assertEqual(graph[subtasks[0].id], [])

    def test_estimate_effort_total(self):
        goal = Goal(name="X", acceptance_criteria=["A", "B", "C"])
        subtasks = self.gen.generate(goal)
        total = self.gen.estimate_effort(subtasks)
        self.assertGreater(total, 0)

    def test_effort_short_vs_long(self):
        goal_short = Goal(name="X", acceptance_criteria=["Do it"])
        goal_long = Goal(name="X", acceptance_criteria=["Implement a comprehensive user authentication system with OAuth support"])
        short_tasks = self.gen.generate(goal_short)
        long_tasks = self.gen.generate(goal_long)
        self.assertLessEqual(short_tasks[0].effort_estimate, long_tasks[0].effort_estimate)

    def test_generate_empty_goal_name(self):
        goal = Goal(name="")
        subtasks = self.gen.generate(goal)
        self.assertEqual(len(subtasks), 1)
        self.assertEqual(subtasks[0].description, "Complete goal")


class TestSubtaskDataclass(unittest.TestCase):
    def test_defaults(self):
        s = Subtask(id="st-abc", description="task")
        self.assertEqual(s.depends_on, [])
        self.assertEqual(s.effort_estimate, 1.0)


if __name__ == "__main__":
    unittest.main()
