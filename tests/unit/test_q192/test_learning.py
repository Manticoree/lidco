"""Tests for LearningStyle and Quiz — task 1074."""
from __future__ import annotations

import unittest

from lidco.output.learning import LearningStyle, Quiz
from lidco.output.style_registry import OutputStyle


class TestQuizFrozen(unittest.TestCase):
    def test_frozen(self):
        q = Quiz(question="Q?", options=("A", "B"), answer_index=0, explanation="E")
        with self.assertRaises(AttributeError):
            q.question = "new"  # type: ignore[misc]

    def test_fields(self):
        q = Quiz(question="Q?", options=("A", "B"), answer_index=1, explanation="E")
        self.assertEqual(q.question, "Q?")
        self.assertEqual(q.options, ("A", "B"))
        self.assertEqual(q.answer_index, 1)
        self.assertEqual(q.explanation, "E")

    def test_equality(self):
        q1 = Quiz(question="Q", options=("A",), answer_index=0, explanation="E")
        q2 = Quiz(question="Q", options=("A",), answer_index=0, explanation="E")
        self.assertEqual(q1, q2)


class TestLearningProtocol(unittest.TestCase):
    def test_is_output_style(self):
        self.assertIsInstance(LearningStyle(), OutputStyle)


class TestLearningName(unittest.TestCase):
    def test_name(self):
        self.assertEqual(LearningStyle().name, "learning")


class TestLearningTransform(unittest.TestCase):
    def test_appends_hint(self):
        result = LearningStyle().transform("Some code explanation")
        self.assertIn("Hint", result)
        self.assertIn("Some code explanation", result)

    def test_empty_passthrough(self):
        self.assertEqual(LearningStyle().transform(""), "")

    def test_whitespace_passthrough(self):
        self.assertEqual(LearningStyle().transform("   "), "   ")


class TestLearningWrapResponse(unittest.TestCase):
    def test_wraps_with_markers(self):
        result = LearningStyle().wrap_response("Content")
        self.assertIn("Learning Mode", result)
        self.assertIn("Content", result)

    def test_empty_response(self):
        self.assertEqual(LearningStyle().wrap_response(""), "")


class TestGenerateQuiz(unittest.TestCase):
    def test_returns_quiz(self):
        q = LearningStyle().generate_quiz("loops", "for i in range(10): pass")
        self.assertIsInstance(q, Quiz)

    def test_quiz_has_options(self):
        q = LearningStyle().generate_quiz("functions", "def foo(): pass")
        self.assertGreater(len(q.options), 0)

    def test_quiz_topic_in_question(self):
        q = LearningStyle().generate_quiz("recursion", "def f(n): return f(n-1)")
        self.assertIn("recursion", q.question)

    def test_quiz_answer_index_valid(self):
        q = LearningStyle().generate_quiz("lists", "x = [1,2,3]")
        self.assertGreaterEqual(q.answer_index, 0)
        self.assertLess(q.answer_index, len(q.options))


class TestProgressiveHint(unittest.TestCase):
    def test_level_0_vague(self):
        result = LearningStyle().progressive_hint("sorting", 0)
        self.assertIn("sorting", result)
        self.assertIn("high level", result)

    def test_level_1(self):
        result = LearningStyle().progressive_hint("sorting", 1)
        self.assertIn("inputs", result)

    def test_level_2(self):
        result = LearningStyle().progressive_hint("sorting", 2)
        self.assertIn("key operation", result)

    def test_level_3_explicit(self):
        result = LearningStyle().progressive_hint("sorting", 3)
        self.assertIn("Direct answer", result)

    def test_negative_level_treated_as_zero(self):
        result = LearningStyle().progressive_hint("test", -1)
        self.assertIn("high level", result)
