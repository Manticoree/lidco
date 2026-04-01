"""Tests for budget.ab_comparator."""
from __future__ import annotations

import unittest

from lidco.budget.ab_comparator import ABComparator, ComparisonResult


class TestComparisonResult(unittest.TestCase):
    def test_frozen(self) -> None:
        cr = ComparisonResult(label_a="a", label_b="b")
        with self.assertRaises(AttributeError):
            cr.winner = "c"  # type: ignore[misc]

    def test_defaults(self) -> None:
        cr = ComparisonResult(label_a="a", label_b="b")
        self.assertEqual(cr.tokens_a, 0)
        self.assertEqual(cr.tokens_b, 0)
        self.assertEqual(cr.efficiency_a, 0.0)
        self.assertEqual(cr.efficiency_b, 0.0)
        self.assertEqual(cr.cost_a, 0.0)
        self.assertEqual(cr.cost_b, 0.0)
        self.assertEqual(cr.winner, "")
        self.assertEqual(cr.savings, 0.0)


class TestABComparator(unittest.TestCase):
    def setUp(self) -> None:
        self.comp = ABComparator()

    def test_compare_higher_efficiency_wins(self) -> None:
        result = self.comp.compare("A", 1000, 0.9, 0.05, "B", 1000, 0.5, 0.05)
        self.assertEqual(result.winner, "A")

    def test_compare_lower_cost_wins_similar_efficiency(self) -> None:
        result = self.comp.compare("A", 1000, 0.8, 0.10, "B", 1000, 0.8, 0.03)
        self.assertEqual(result.winner, "B")

    def test_compare_savings_computed(self) -> None:
        result = self.comp.compare("A", 1000, 0.8, 0.10, "B", 1000, 0.7, 0.05)
        self.assertAlmostEqual(result.savings, 0.05)

    def test_compare_models_dict(self) -> None:
        stats_a = {"tokens": 5000, "efficiency": 0.7, "cost": 0.10}
        stats_b = {"tokens": 3000, "efficiency": 0.9, "cost": 0.08}
        result = self.comp.compare_models("gpt-4", stats_a, "claude", stats_b)
        self.assertEqual(result.label_a, "gpt-4")
        self.assertEqual(result.label_b, "claude")
        self.assertEqual(result.winner, "claude")

    def test_compare_models_missing_keys(self) -> None:
        result = self.comp.compare_models("a", {}, "b", {})
        self.assertIn(result.winner, ("a", "b"))

    def test_get_comparisons(self) -> None:
        self.comp.compare("A", 100, 0.5, 0.01, "B", 100, 0.6, 0.01)
        self.comp.compare("C", 100, 0.7, 0.02, "D", 100, 0.3, 0.01)
        self.assertEqual(len(self.comp.get_comparisons()), 2)

    def test_best_of(self) -> None:
        r1 = self.comp.compare("A", 100, 0.9, 0.05, "B", 100, 0.5, 0.05)
        r2 = self.comp.compare("A", 200, 0.8, 0.06, "B", 200, 0.4, 0.06)
        r3 = self.comp.compare("A", 300, 0.3, 0.04, "B", 300, 0.7, 0.04)
        best = self.comp.best_of([r1, r2, r3])
        self.assertEqual(best, "A")

    def test_best_of_empty(self) -> None:
        self.assertEqual(self.comp.best_of([]), "")

    def test_summary(self) -> None:
        result = self.comp.compare("A", 1000, 0.8, 0.05, "B", 1000, 0.6, 0.03)
        s = self.comp.summary(result)
        self.assertIn("A vs B", s)
        self.assertIn("winner:", s)
        self.assertIn("savings:", s)

    def test_immutable_internal_list(self) -> None:
        self.comp.compare("A", 100, 0.5, 0.01, "B", 100, 0.6, 0.01)
        comps = self.comp.get_comparisons()
        comps.clear()
        self.assertEqual(len(self.comp.get_comparisons()), 1)


if __name__ == "__main__":
    unittest.main()
