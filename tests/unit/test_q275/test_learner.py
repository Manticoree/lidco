"""Tests for lidco.recovery.learner."""
from __future__ import annotations

import unittest

from lidco.recovery.learner import ErrorPatternLearner, Resolution


class TestErrorPatternLearner(unittest.TestCase):
    def setUp(self):
        self.learner = ErrorPatternLearner()

    def test_record_resolution_new(self):
        res = self.learner.record_resolution("KeyError", "check key exists", True)
        self.assertEqual(res.success_count, 1)
        self.assertEqual(res.failure_count, 0)

    def test_record_resolution_accumulates(self):
        self.learner.record_resolution("KeyError", "check key", True)
        res = self.learner.record_resolution("KeyError", "check key", False)
        self.assertEqual(res.success_count, 1)
        self.assertEqual(res.failure_count, 1)

    def test_suggest_matches(self):
        self.learner.record_resolution("KeyError", "fix A", True)
        self.learner.record_resolution("TypeError", "fix B", True)
        suggestions = self.learner.suggest("KeyError: 'x'")
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].fix_description, "fix A")

    def test_suggest_empty(self):
        suggestions = self.learner.suggest("no match")
        self.assertEqual(suggestions, [])

    def test_best_fix(self):
        self.learner.record_resolution("Timeout", "increase timeout", True)
        self.learner.record_resolution("Timeout", "increase timeout", True)
        self.learner.record_resolution("Timeout", "retry later", True)
        best = self.learner.best_fix("Timeout occurred")
        self.assertIsNotNone(best)
        self.assertEqual(best.fix_description, "increase timeout")

    def test_best_fix_none(self):
        self.assertIsNone(self.learner.best_fix("nothing"))

    def test_success_rate(self):
        self.learner.record_resolution("Err", "fix", True)
        self.learner.record_resolution("Err", "fix", False)
        rate = self.learner.success_rate("Err")
        self.assertAlmostEqual(rate, 0.5)

    def test_success_rate_no_data(self):
        self.assertEqual(self.learner.success_rate("nope"), 0.0)

    def test_all_resolutions(self):
        self.learner.record_resolution("A", "fix A", True)
        self.learner.record_resolution("B", "fix B", False)
        self.assertEqual(len(self.learner.all_resolutions()), 2)

    def test_top_fixes(self):
        self.learner.record_resolution("A", "fix A", True)
        self.learner.record_resolution("B", "fix B", False)
        top = self.learner.top_fixes(limit=1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0].error_pattern, "A")

    def test_summary(self):
        self.learner.record_resolution("X", "fix", True)
        s = self.learner.summary()
        self.assertIn("resolution_count", s)
        self.assertEqual(s["resolution_count"], 1)
        self.assertIn("overall_success_rate", s)

    def test_resolution_dataclass(self):
        r = Resolution(error_pattern="e", fix_description="f")
        self.assertEqual(r.success_count, 0)
        self.assertEqual(r.failure_count, 0)


if __name__ == "__main__":
    unittest.main()
