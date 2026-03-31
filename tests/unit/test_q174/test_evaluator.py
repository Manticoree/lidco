"""Tests for ResultEvaluator."""
from __future__ import annotations

import unittest

from lidco.explore.evaluator import (
    EvaluationCriteria,
    EvaluationResult,
    EvaluationWeights,
    ResultEvaluator,
)


class TestEvaluationWeights(unittest.TestCase):
    def test_default_weights(self) -> None:
        w = EvaluationWeights()
        self.assertAlmostEqual(w.tests, 0.35)
        self.assertAlmostEqual(w.lint, 0.15)
        self.assertAlmostEqual(w.diff_size, 0.20)
        self.assertAlmostEqual(w.complexity, 0.15)
        self.assertAlmostEqual(w.cost, 0.10)
        self.assertAlmostEqual(w.errors, 0.05)

    def test_weights_sum_to_one(self) -> None:
        w = EvaluationWeights()
        total = w.tests + w.lint + w.diff_size + w.complexity + w.cost + w.errors
        self.assertAlmostEqual(total, 1.0)


class TestResultEvaluator(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = ResultEvaluator()

    def test_weights_property(self) -> None:
        self.assertIsInstance(self.evaluator.weights, EvaluationWeights)

    def test_evaluate_perfect_score(self) -> None:
        criteria = EvaluationCriteria(
            tests_passed=True,
            lint_clean=True,
            diff_lines=0,
            complexity_delta=-5,
            token_cost=0,
            error_count=0,
        )
        result = self.evaluator.evaluate("v1", criteria)
        self.assertGreater(result.total_score, 0.9)
        self.assertEqual(result.variant_id, "v1")

    def test_evaluate_all_bad(self) -> None:
        criteria = EvaluationCriteria(
            tests_passed=False,
            lint_clean=False,
            diff_lines=1000,
            complexity_delta=10,
            token_cost=20000,
            error_count=20,
        )
        result = self.evaluator.evaluate("v1", criteria)
        self.assertLess(result.total_score, 0.1)

    def test_evaluate_tests_passed_vs_failed(self) -> None:
        passed = self.evaluator.evaluate("v1", EvaluationCriteria(tests_passed=True))
        failed = self.evaluator.evaluate("v2", EvaluationCriteria(tests_passed=False))
        self.assertGreater(passed.total_score, failed.total_score)

    def test_evaluate_lint_clean(self) -> None:
        clean = self.evaluator.evaluate("v1", EvaluationCriteria(lint_clean=True))
        dirty = self.evaluator.evaluate("v2", EvaluationCriteria(lint_clean=False))
        self.assertGreater(clean.total_score, dirty.total_score)

    def test_evaluate_small_diff_better(self) -> None:
        small = self.evaluator.evaluate("v1", EvaluationCriteria(diff_lines=10))
        large = self.evaluator.evaluate("v2", EvaluationCriteria(diff_lines=400))
        self.assertGreater(small.total_score, large.total_score)

    def test_evaluate_complexity_reduction(self) -> None:
        reduced = self.evaluator.evaluate("v1", EvaluationCriteria(complexity_delta=-3))
        increased = self.evaluator.evaluate("v2", EvaluationCriteria(complexity_delta=3))
        self.assertGreater(reduced.total_score, increased.total_score)

    def test_evaluate_complexity_neutral(self) -> None:
        neutral = self.evaluator.evaluate("v1", EvaluationCriteria(complexity_delta=0))
        increased = self.evaluator.evaluate("v2", EvaluationCriteria(complexity_delta=5))
        self.assertGreater(neutral.total_score, increased.total_score)

    def test_evaluate_low_cost(self) -> None:
        low = self.evaluator.evaluate("v1", EvaluationCriteria(token_cost=100))
        high = self.evaluator.evaluate("v2", EvaluationCriteria(token_cost=9000))
        self.assertGreater(low.total_score, high.total_score)

    def test_evaluate_no_errors(self) -> None:
        clean = self.evaluator.evaluate("v1", EvaluationCriteria(error_count=0))
        errors = self.evaluator.evaluate("v2", EvaluationCriteria(error_count=5))
        self.assertGreater(clean.total_score, errors.total_score)

    def test_evaluate_breakdown_keys(self) -> None:
        result = self.evaluator.evaluate("v1", EvaluationCriteria())
        expected_keys = {"tests", "lint", "diff_size", "complexity", "cost", "errors"}
        self.assertEqual(set(result.breakdown.keys()), expected_keys)

    def test_rank_variants(self) -> None:
        e1 = self.evaluator.evaluate("v1", EvaluationCriteria(tests_passed=True, lint_clean=True))
        e2 = self.evaluator.evaluate("v2", EvaluationCriteria(tests_passed=False, lint_clean=False))
        ranked = self.evaluator.rank_variants([e2, e1])
        self.assertEqual(ranked[0].variant_id, "v1")
        self.assertEqual(ranked[0].rank, 1)
        self.assertEqual(ranked[1].rank, 2)

    def test_rank_empty(self) -> None:
        ranked = self.evaluator.rank_variants([])
        self.assertEqual(ranked, [])

    def test_pick_winner(self) -> None:
        e1 = self.evaluator.evaluate("v1", EvaluationCriteria(tests_passed=True))
        e2 = self.evaluator.evaluate("v2", EvaluationCriteria(tests_passed=False))
        winner = self.evaluator.pick_winner([e1, e2])
        self.assertIsNotNone(winner)
        self.assertEqual(winner.variant_id, "v1")
        self.assertEqual(winner.rank, 1)

    def test_pick_winner_empty(self) -> None:
        self.assertIsNone(self.evaluator.pick_winner([]))

    def test_recommendation_text_winner(self) -> None:
        e1 = self.evaluator.evaluate("v1", EvaluationCriteria(tests_passed=True, lint_clean=True))
        ranked = self.evaluator.rank_variants([e1])
        self.assertIn("Winner", ranked[0].recommendation)

    def test_strong_alternative(self) -> None:
        # Two evaluations with close scores
        e1 = self.evaluator.evaluate("v1", EvaluationCriteria(tests_passed=True, lint_clean=True))
        e2 = self.evaluator.evaluate("v2", EvaluationCriteria(tests_passed=True, lint_clean=False))
        ranked = self.evaluator.rank_variants([e1, e2])
        # e2 should be "Strong alternative" if within 90% of winner
        if ranked[1].total_score >= ranked[0].total_score * 0.9:
            self.assertEqual(ranked[1].recommendation, "Strong alternative")

    def test_lower_priority(self) -> None:
        e1 = self.evaluator.evaluate(
            "v1",
            EvaluationCriteria(tests_passed=True, lint_clean=True, complexity_delta=-5),
        )
        e2 = self.evaluator.evaluate(
            "v2",
            EvaluationCriteria(tests_passed=False, lint_clean=False, complexity_delta=10, error_count=9),
        )
        ranked = self.evaluator.rank_variants([e1, e2])
        self.assertEqual(ranked[1].recommendation, "Lower priority")

    def test_custom_weights(self) -> None:
        weights = EvaluationWeights(tests=1.0, lint=0.0, diff_size=0.0, complexity=0.0, cost=0.0, errors=0.0)
        evaluator = ResultEvaluator(weights)
        r = evaluator.evaluate("v1", EvaluationCriteria(tests_passed=True))
        self.assertAlmostEqual(r.total_score, 1.0)


if __name__ == "__main__":
    unittest.main()
