"""Tests for lidco.goals.validator."""
from __future__ import annotations

import unittest

from lidco.goals.parser import Goal
from lidco.goals.validator import GoalValidator, ValidationResult


class TestGoalValidator(unittest.TestCase):
    def setUp(self):
        self.validator = GoalValidator()

    def test_validate_all_pass(self):
        goal = Goal(name="Auth", acceptance_criteria=["Login works", "Logout works"])
        results = {"Login works": True, "Logout works": True}
        vr = self.validator.validate(goal, results)
        self.assertTrue(vr.passed)
        self.assertEqual(len(vr.criteria_met), 2)
        self.assertEqual(len(vr.criteria_failed), 0)

    def test_validate_all_fail(self):
        goal = Goal(name="Auth", acceptance_criteria=["Login works", "Logout works"])
        results = {"Login works": False, "Logout works": False}
        vr = self.validator.validate(goal, results)
        self.assertFalse(vr.passed)
        self.assertEqual(len(vr.criteria_failed), 2)

    def test_validate_partial_fail(self):
        goal = Goal(name="Auth", acceptance_criteria=["Login works", "Logout works"])
        results = {"Login works": True, "Logout works": False}
        vr = self.validator.validate(goal, results)
        self.assertFalse(vr.passed)
        self.assertEqual(len(vr.criteria_met), 1)
        self.assertEqual(len(vr.criteria_failed), 1)

    def test_validate_no_criteria(self):
        goal = Goal(name="Empty")
        results: dict[str, bool] = {}
        vr = self.validator.validate(goal, results)
        self.assertFalse(vr.passed)

    def test_validate_substring_match(self):
        goal = Goal(name="X", acceptance_criteria=["Login works"])
        results = {"Login works correctly": True}
        vr = self.validator.validate(goal, results)
        self.assertTrue(vr.passed)

    def test_validate_missing_results(self):
        goal = Goal(name="X", acceptance_criteria=["A", "B"])
        results = {"A": True}
        vr = self.validator.validate(goal, results)
        self.assertFalse(vr.passed)
        self.assertIn("B", vr.criteria_failed)

    def test_validate_partial_threshold_pass(self):
        goal = Goal(name="X", acceptance_criteria=["A", "B", "C"])
        results = {"A": True, "B": True, "C": False}
        vr = self.validator.validate_partial(goal, results, threshold=0.5)
        self.assertTrue(vr.passed)

    def test_validate_partial_threshold_fail(self):
        goal = Goal(name="X", acceptance_criteria=["A", "B", "C"])
        results = {"A": True, "B": False, "C": False}
        vr = self.validator.validate_partial(goal, results, threshold=0.8)
        self.assertFalse(vr.passed)

    def test_validate_partial_no_criteria(self):
        goal = Goal(name="X")
        vr = self.validator.validate_partial(goal, {})
        self.assertFalse(vr.passed)

    def test_validate_case_insensitive_match(self):
        goal = Goal(name="X", acceptance_criteria=["login WORKS"])
        results = {"Login Works": True}
        vr = self.validator.validate(goal, results)
        self.assertTrue(vr.passed)


class TestValidationResult(unittest.TestCase):
    def test_defaults(self):
        vr = ValidationResult(passed=True)
        self.assertEqual(vr.criteria_met, [])
        self.assertEqual(vr.criteria_failed, [])


if __name__ == "__main__":
    unittest.main()
