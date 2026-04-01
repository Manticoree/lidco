"""Tests for budget.optimization_advisor."""
from __future__ import annotations

import unittest

from lidco.budget.optimization_advisor import (
    OptimizationAdvisor,
    Priority,
    Recommendation,
)


class TestPriority(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(Priority.HIGH, "high")
        self.assertEqual(Priority.MEDIUM, "medium")
        self.assertEqual(Priority.LOW, "low")


class TestRecommendation(unittest.TestCase):
    def test_frozen(self) -> None:
        rec = Recommendation(action="test")
        with self.assertRaises(AttributeError):
            rec.action = "x"  # type: ignore[misc]

    def test_defaults(self) -> None:
        rec = Recommendation(action="test")
        self.assertEqual(rec.priority, Priority.MEDIUM)
        self.assertEqual(rec.estimated_savings, 0)
        self.assertEqual(rec.description, "")


class TestOptimizationAdvisor(unittest.TestCase):
    def setUp(self) -> None:
        self.advisor = OptimizationAdvisor()

    def test_auto_compaction_recommendation(self) -> None:
        recs = self.advisor.analyze(total_tokens=100000, context_limit=128000, compactions=0)
        actions = [r.action for r in recs]
        self.assertIn("Enable auto-compaction", actions)

    def test_no_auto_compaction_if_low_util(self) -> None:
        recs = self.advisor.analyze(total_tokens=10000, context_limit=128000, compactions=0)
        actions = [r.action for r in recs]
        self.assertNotIn("Enable auto-compaction", actions)

    def test_reduce_tool_size(self) -> None:
        recs = self.advisor.analyze(
            total_tokens=1000, context_limit=2000, compactions=1,
            tool_usage={"search": 400},
        )
        actions = [r.action for r in recs]
        self.assertIn("Reduce tool result size", actions)

    def test_cheaper_model_if_underutilized(self) -> None:
        recs = self.advisor.analyze(total_tokens=10000, context_limit=128000, compactions=0)
        actions = [r.action for r in recs]
        self.assertIn("Use cheaper model", actions)

    def test_increase_compaction_frequency(self) -> None:
        recs = self.advisor.analyze(total_tokens=110000, context_limit=128000, compactions=2)
        actions = [r.action for r in recs]
        self.assertIn("Increase compaction frequency", actions)

    def test_batch_tool_calls(self) -> None:
        recs = self.advisor.analyze(
            total_tokens=50000, context_limit=128000, compactions=1, turns=25,
        )
        actions = [r.action for r in recs]
        self.assertIn("Consider batch tool calls", actions)

    def test_no_batch_if_few_turns(self) -> None:
        recs = self.advisor.analyze(total_tokens=50000, context_limit=128000, compactions=1, turns=5)
        actions = [r.action for r in recs]
        self.assertNotIn("Consider batch tool calls", actions)

    def test_get_recommendations_accumulates(self) -> None:
        self.advisor.analyze(total_tokens=100000, context_limit=128000, compactions=0)
        self.advisor.analyze(total_tokens=100000, context_limit=128000, compactions=0)
        all_recs = self.advisor.get_recommendations()
        self.assertTrue(len(all_recs) >= 2)

    def test_top_returns_highest_priority(self) -> None:
        self.advisor.analyze(
            total_tokens=100000, context_limit=128000, compactions=0, turns=25,
        )
        top = self.advisor.top(2)
        self.assertTrue(len(top) <= 2)
        if len(top) >= 2:
            self.assertLessEqual(
                list(Priority).index(top[0].priority),
                list(Priority).index(top[1].priority),
            )

    def test_total_potential_savings(self) -> None:
        self.advisor.analyze(total_tokens=100000, context_limit=128000, compactions=0)
        self.assertGreater(self.advisor.total_potential_savings(), 0)

    def test_summary_empty(self) -> None:
        s = self.advisor.summary()
        self.assertIn("No optimization", s)

    def test_summary_with_recs(self) -> None:
        self.advisor.analyze(total_tokens=100000, context_limit=128000, compactions=0)
        s = self.advisor.summary()
        self.assertIn("recommendations", s)
        self.assertIn("savings", s)


if __name__ == "__main__":
    unittest.main()
