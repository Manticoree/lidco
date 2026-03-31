"""Tests for Q152 SolutionSuggester."""
from __future__ import annotations

import unittest

from lidco.errors.solution_suggester import SolutionSuggester, Solution


class TestSolution(unittest.TestCase):
    def test_fields(self):
        s = Solution(title="Fix", steps=["a", "b"], confidence=0.8, category="gen")
        self.assertEqual(s.title, "Fix")
        self.assertEqual(len(s.steps), 2)
        self.assertEqual(s.confidence, 0.8)
        self.assertEqual(s.category, "gen")


class TestSolutionSuggester(unittest.TestCase):
    def setUp(self):
        self.ss = SolutionSuggester()

    def test_suggest_no_solutions(self):
        self.assertEqual(self.ss.suggest(RuntimeError("x")), [])

    def test_add_and_suggest(self):
        self.ss.add_solution(r"RuntimeError", "Fix runtime", ["step1"], "general")
        sols = self.ss.suggest(RuntimeError("boom"))
        self.assertEqual(len(sols), 1)
        self.assertEqual(sols[0].title, "Fix runtime")

    def test_suggest_no_match(self):
        self.ss.add_solution(r"KeyError", "Fix key", ["s1"])
        sols = self.ss.suggest(ValueError("bad"))
        self.assertEqual(sols, [])

    def test_suggest_multiple_matches(self):
        self.ss.add_solution(r"Error", "Generic", ["s1"])
        self.ss.add_solution(r"ValueError", "Specific", ["s1"])
        sols = self.ss.suggest(ValueError("bad"))
        self.assertEqual(len(sols), 2)

    def test_suggest_sorted_by_confidence(self):
        self.ss.add_solution(r"ValueError", "Specific", ["s1"])
        self.ss.add_solution(r"Error", "Generic", ["s1"])
        sols = self.ss.suggest(ValueError("bad"))
        self.assertGreaterEqual(sols[0].confidence, sols[1].confidence)

    def test_suggest_case_insensitive(self):
        self.ss.add_solution(r"valueerror", "Fix", ["s1"])
        sols = self.ss.suggest(ValueError("x"))
        self.assertEqual(len(sols), 1)

    def test_suggest_with_context(self):
        self.ss.add_solution(r"Error", "Fix", ["s1"], "network")
        sols = self.ss.suggest(RuntimeError("x"), {"categories": ["network"]})
        self.assertEqual(len(sols), 1)
        # Confidence should be boosted
        self.assertGreater(sols[0].confidence, 0)

    def test_best_returns_top(self):
        self.ss.add_solution(r"Error", "A", ["s1"])
        self.ss.add_solution(r"RuntimeError", "B", ["s1"])
        best = self.ss.best(RuntimeError("x"))
        self.assertIsNotNone(best)

    def test_best_returns_none_when_empty(self):
        self.assertIsNone(self.ss.best(RuntimeError("x")))

    def test_confidence_bounded(self):
        self.ss.add_solution(r".*", "All", ["s1"])
        sols = self.ss.suggest(RuntimeError("x"))
        self.assertLessEqual(sols[0].confidence, 1.0)

    def test_format_solutions_empty(self):
        out = self.ss.format_solutions([])
        self.assertIn("No solutions", out)

    def test_format_solutions_numbered(self):
        sols = [
            Solution("Fix A", ["step1", "step2"], 0.9, "gen"),
            Solution("Fix B", ["step3"], 0.5, "gen"),
        ]
        out = self.ss.format_solutions(sols)
        self.assertIn("1. Fix A", out)
        self.assertIn("2. Fix B", out)
        self.assertIn("step1", out)
        self.assertIn("step3", out)

    def test_format_solutions_shows_confidence(self):
        sols = [Solution("T", ["s"], 0.75, "cat")]
        out = self.ss.format_solutions(sols)
        self.assertIn("75%", out)

    def test_add_default_category(self):
        self.ss.add_solution(r"Err", "Fix", ["s1"])
        sols = self.ss.suggest(RuntimeError("Err"))
        self.assertEqual(sols[0].category, "general")

    def test_steps_are_copies(self):
        original = ["s1"]
        self.ss.add_solution(r"Err", "Fix", original)
        original.append("s2")
        sols = self.ss.suggest(RuntimeError("Err"))
        self.assertEqual(len(sols[0].steps), 1)


class TestWithDefaults(unittest.TestCase):
    def setUp(self):
        self.ss = SolutionSuggester.with_defaults()

    def test_module_not_found(self):
        sols = self.ss.suggest(ModuleNotFoundError("No module named foo"))
        self.assertGreater(len(sols), 0)

    def test_file_not_found(self):
        sols = self.ss.suggest(FileNotFoundError("missing"))
        self.assertGreater(len(sols), 0)

    def test_permission_error(self):
        best = self.ss.best(PermissionError("denied"))
        self.assertIsNotNone(best)

    def test_key_error(self):
        sols = self.ss.suggest(KeyError("x"))
        self.assertGreater(len(sols), 0)

    def test_type_error(self):
        sols = self.ss.suggest(TypeError("wrong"))
        self.assertGreater(len(sols), 0)


if __name__ == "__main__":
    unittest.main()
