"""Tests for budget.task_scorer."""
from __future__ import annotations

import unittest

from lidco.budget.task_scorer import Complexity, TaskScore, TaskScorer


class TestComplexity(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Complexity.SIMPLE, "simple")
        self.assertEqual(Complexity.MODERATE, "moderate")
        self.assertEqual(Complexity.COMPLEX, "complex")
        self.assertEqual(Complexity.EXPERT, "expert")


class TestTaskScore(unittest.TestCase):
    def test_frozen(self):
        s = TaskScore(complexity=Complexity.SIMPLE)
        with self.assertRaises(AttributeError):
            s.score = 1.0  # type: ignore[misc]

    def test_defaults(self):
        s = TaskScore(complexity=Complexity.MODERATE)
        self.assertEqual(s.score, 0.0)
        self.assertEqual(s.indicators, ())
        self.assertEqual(s.suggested_max_tokens, 4096)


class TestTaskScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = TaskScorer()

    def test_empty_prompt(self):
        result = self.scorer.score("")
        self.assertEqual(result.complexity, Complexity.SIMPLE)
        self.assertAlmostEqual(result.score, 0.0)

    def test_simple_prompt(self):
        result = self.scorer.score("what is a list?")
        self.assertEqual(result.complexity, Complexity.SIMPLE)
        self.assertIn("what-is question", result.indicators)
        self.assertEqual(result.suggested_max_tokens, 1024)

    def test_moderate_prompt(self):
        result = self.scorer.score("fix the bug in `utils.py` and update the handler")
        self.assertIn(result.complexity, (Complexity.MODERATE, Complexity.COMPLEX))
        self.assertIn("fix request", result.indicators)

    def test_complex_prompt(self):
        result = self.scorer.score("refactor the module and implement a new parser step 1 then step 2")
        self.assertIn(result.complexity, (Complexity.COMPLEX, Complexity.EXPERT))
        self.assertIn("refactor request", result.indicators)

    def test_expert_prompt(self):
        result = self.scorer.score(
            "rewrite the architecture and design a new system\n"
            "```python\nclass Foo: pass\n```\n"
        )
        self.assertIn(result.complexity, (Complexity.COMPLEX, Complexity.EXPERT))
        self.assertIn("rewrite request", result.indicators)
        self.assertIn("code block", result.indicators)
        self.assertGreaterEqual(result.score, 0.5)

    def test_suggest_max_tokens_values(self):
        self.assertEqual(TaskScorer.suggest_max_tokens(Complexity.SIMPLE), 1024)
        self.assertEqual(TaskScorer.suggest_max_tokens(Complexity.MODERATE), 4096)
        self.assertEqual(TaskScorer.suggest_max_tokens(Complexity.COMPLEX), 8192)
        self.assertEqual(TaskScorer.suggest_max_tokens(Complexity.EXPERT), 16384)

    def test_summary_format(self):
        result = self.scorer.score("explain decorators")
        text = self.scorer.summary(result)
        self.assertIn("TaskScore:", text)
        self.assertIn("Complexity:", text)
        self.assertIn("Score:", text)

    def test_indicators_detected(self):
        indicators = self.scorer._detect_indicators("fix a bug in `main.py`")
        self.assertIn("fix request", indicators)
        self.assertIn("code mention", indicators)

    def test_short_prompt_simple(self):
        result = self.scorer.score("hello")
        self.assertEqual(result.complexity, Complexity.SIMPLE)


if __name__ == "__main__":
    unittest.main()
