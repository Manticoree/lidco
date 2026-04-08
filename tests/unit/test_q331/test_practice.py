"""Tests for lidco.learning.practice -- PracticeGenerator, Exercise, grading."""
from __future__ import annotations

import unittest

from lidco.learning.practice import (
    Exercise,
    PracticeGenerator,
    Submission,
    default_grader,
)


class TestDefaultGrader(unittest.TestCase):
    def test_perfect_match(self) -> None:
        passed, score, feedback = default_grader("hello", "hello")
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 1.0)
        self.assertIn("Perfect", feedback)

    def test_whitespace_normalization(self) -> None:
        passed, score, _ = default_grader("  hello  ", "hello")
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 1.0)

    def test_partial_match(self) -> None:
        passed, score, feedback = default_grader("line1\nline2", "line1\nline2\nline3\nline4\nline5")
        self.assertLess(score, 1.0)
        self.assertIn("lines", feedback)

    def test_no_solution(self) -> None:
        passed, score, _ = default_grader("code", "")
        self.assertFalse(passed)

    def test_high_partial_passes(self) -> None:
        sol = "a\nb\nc\nd\ne"
        user = "a\nb\nc\nd\ne"
        passed, score, _ = default_grader(user, sol)
        self.assertTrue(passed)


class TestExercise(unittest.TestCase):
    def test_hint_valid(self) -> None:
        e = Exercise(exercise_id="1", title="T", description="D", hints=["h1", "h2"])
        self.assertEqual(e.hint(0), "h1")
        self.assertEqual(e.hint(1), "h2")

    def test_hint_out_of_range(self) -> None:
        e = Exercise(exercise_id="1", title="T", description="D")
        self.assertEqual(e.hint(0), "No hint available.")


class TestPracticeGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.gen = PracticeGenerator()

    def test_add_and_get_exercise(self) -> None:
        ex = Exercise(exercise_id="e1", title="Test", description="Desc")
        self.gen.add_exercise(ex)
        self.assertIs(self.gen.get_exercise("e1"), ex)

    def test_get_missing(self) -> None:
        self.assertIsNone(self.gen.get_exercise("missing"))

    def test_generate_from_pattern(self) -> None:
        ex = self.gen.generate_from_pattern("singleton", "class S: pass", difficulty=3, skill="python")
        self.assertIn("singleton", ex.title)
        self.assertEqual(ex.difficulty, 3)
        self.assertEqual(ex.skill, "python")
        self.assertIsNotNone(self.gen.get_exercise(ex.exercise_id))

    def test_generate_clamps_difficulty(self) -> None:
        ex = self.gen.generate_from_pattern("p", "code", difficulty=10)
        self.assertEqual(ex.difficulty, 5)
        ex2 = self.gen.generate_from_pattern("p2", "code2", difficulty=-1)
        self.assertEqual(ex2.difficulty, 1)

    def test_list_exercises_all(self) -> None:
        self.gen.generate_from_pattern("a", "code_a", skill="python")
        self.gen.generate_from_pattern("b", "code_b", skill="go")
        self.assertEqual(len(self.gen.list_exercises()), 2)

    def test_list_exercises_filter_skill(self) -> None:
        self.gen.generate_from_pattern("a", "code_a", skill="python")
        self.gen.generate_from_pattern("b", "code_b", skill="go")
        self.assertEqual(len(self.gen.list_exercises(skill="python")), 1)

    def test_list_exercises_filter_difficulty(self) -> None:
        self.gen.generate_from_pattern("a", "code_a", difficulty=1)
        self.gen.generate_from_pattern("b", "code_b", difficulty=3)
        self.assertEqual(len(self.gen.list_exercises(difficulty=1)), 1)

    def test_submit_pass(self) -> None:
        ex = self.gen.generate_from_pattern("p", "hello world")
        sub = self.gen.submit(ex.exercise_id, "hello world")
        self.assertTrue(sub.passed)
        self.assertAlmostEqual(sub.score, 1.0)

    def test_submit_fail(self) -> None:
        ex = self.gen.generate_from_pattern("p", "expected")
        sub = self.gen.submit(ex.exercise_id, "totally wrong")
        self.assertFalse(sub.passed)

    def test_submit_missing_exercise(self) -> None:
        sub = self.gen.submit("nonexistent", "code")
        self.assertFalse(sub.passed)
        self.assertIn("not found", sub.feedback)

    def test_submissions_tracked(self) -> None:
        ex = self.gen.generate_from_pattern("p", "code")
        self.gen.submit(ex.exercise_id, "code")
        self.gen.submit(ex.exercise_id, "wrong")
        self.assertEqual(len(self.gen.submissions), 2)

    def test_stats(self) -> None:
        ex = self.gen.generate_from_pattern("p", "code")
        self.gen.submit(ex.exercise_id, "code")
        self.gen.submit(ex.exercise_id, "wrong")
        s = self.gen.stats()
        self.assertEqual(s["total_submissions"], 2)
        self.assertEqual(s["passed"], 1)
        self.assertEqual(s["exercises_available"], 1)

    def test_format_summary(self) -> None:
        summary = self.gen.format_summary()
        self.assertIn("Exercises", summary)

    def test_custom_grader(self) -> None:
        def always_pass(user: str, sol: str) -> tuple[bool, float, str]:
            return True, 1.0, "Always pass!"

        gen = PracticeGenerator(grader=always_pass)
        ex = Exercise(exercise_id="x", title="T", description="D", solution="sol")
        gen.add_exercise(ex)
        sub = gen.submit("x", "anything")
        self.assertTrue(sub.passed)


if __name__ == "__main__":
    unittest.main()
