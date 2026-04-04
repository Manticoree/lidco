"""Tests for lidco.goals.parser."""
from __future__ import annotations

import unittest

from lidco.goals.parser import Goal, GoalParser


class TestGoalParser(unittest.TestCase):
    def setUp(self):
        self.parser = GoalParser()

    # -- parse ---------------------------------------------------------

    def test_parse_simple_text(self):
        goal = self.parser.parse("Add user authentication")
        self.assertEqual(goal.name, "Add user authentication")
        self.assertEqual(goal.priority, "medium")
        self.assertEqual(goal.acceptance_criteria, [])

    def test_parse_empty_text(self):
        goal = self.parser.parse("")
        self.assertEqual(goal.name, "")
        self.assertEqual(goal.priority, "medium")

    def test_parse_with_criteria_bullets(self):
        text = "Build login page\n- Users can enter email\n- Password field is masked"
        goal = self.parser.parse(text)
        self.assertEqual(goal.name, "Build login page")
        self.assertEqual(len(goal.acceptance_criteria), 2)
        self.assertIn("Users can enter email", goal.acceptance_criteria)

    def test_parse_with_numbered_criteria(self):
        text = "Refactor API\n1. Remove deprecated endpoints\n2. Add versioning"
        goal = self.parser.parse(text)
        self.assertEqual(len(goal.acceptance_criteria), 2)
        self.assertIn("Remove deprecated endpoints", goal.acceptance_criteria)

    def test_parse_high_priority(self):
        goal = self.parser.parse("Fix critical security bug in auth")
        self.assertEqual(goal.priority, "critical")

    def test_parse_low_priority(self):
        goal = self.parser.parse("Minor typo fix in readme")
        self.assertEqual(goal.priority, "low")

    def test_parse_important_keyword(self):
        goal = self.parser.parse("Important: update payment flow")
        self.assertEqual(goal.priority, "high")

    def test_parse_sentence_boundary(self):
        goal = self.parser.parse("Fix the bug. Then add tests for it.")
        self.assertEqual(goal.name, "Fix the bug.")

    # -- extract_criteria ----------------------------------------------

    def test_extract_criteria_dash_bullets(self):
        text = "Goal\n- criterion one\n- criterion two\n- criterion three"
        criteria = self.parser.extract_criteria(text)
        self.assertEqual(len(criteria), 3)
        self.assertEqual(criteria[0], "criterion one")

    def test_extract_criteria_star_bullets(self):
        text = "Goal\n* first\n* second"
        criteria = self.parser.extract_criteria(text)
        self.assertEqual(len(criteria), 2)

    def test_extract_criteria_mixed(self):
        text = "Goal\n- dash item\n1. numbered item\n* star item"
        criteria = self.parser.extract_criteria(text)
        self.assertEqual(len(criteria), 3)

    def test_extract_criteria_no_bullets(self):
        text = "Just a plain goal with no bullets"
        criteria = self.parser.extract_criteria(text)
        self.assertEqual(criteria, [])


class TestGoalDataclass(unittest.TestCase):
    def test_goal_defaults(self):
        g = Goal(name="test")
        self.assertEqual(g.priority, "medium")
        self.assertEqual(g.acceptance_criteria, [])

    def test_goal_custom_fields(self):
        g = Goal(name="x", acceptance_criteria=["a"], priority="high")
        self.assertEqual(g.priority, "high")
        self.assertEqual(g.acceptance_criteria, ["a"])


if __name__ == "__main__":
    unittest.main()
