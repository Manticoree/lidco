"""Tests for budget.pre_call_estimator."""
from __future__ import annotations

import unittest

from lidco.budget.pre_call_estimator import CostEstimate, PreCallEstimator


class TestCostEstimate(unittest.TestCase):
    def test_frozen(self):
        e = CostEstimate(tool_name="Read")
        with self.assertRaises(AttributeError):
            e.tool_name = "Bash"  # type: ignore[misc]

    def test_defaults(self):
        e = CostEstimate(tool_name="t")
        self.assertEqual(e.estimated_tokens, 0)
        self.assertAlmostEqual(e.confidence, 0.5)
        self.assertTrue(e.within_budget)


class TestPreCallEstimator(unittest.TestCase):
    def setUp(self):
        self.estimator = PreCallEstimator()

    def test_default_estimate(self):
        est = self.estimator.estimate("unknown_tool")
        self.assertEqual(est.estimated_tokens, 500)
        self.assertAlmostEqual(est.confidence, 0.5)

    def test_bash_estimate(self):
        est = self.estimator.estimate("Bash")
        self.assertEqual(est.estimated_tokens, 800)

    def test_read_with_size_hint(self):
        est = self.estimator.estimate("Read", args={"size_hint": 4000})
        self.assertEqual(est.estimated_tokens, 1000)

    def test_read_no_hint(self):
        est = self.estimator.estimate("Read")
        self.assertEqual(est.estimated_tokens, 600)

    def test_grep_estimate(self):
        est = self.estimator.estimate("Grep", args={"pattern": "foo"})
        self.assertGreater(est.estimated_tokens, 400)

    def test_record_and_average(self):
        self.estimator.record_actual("Read", 1000)
        self.assertEqual(self.estimator.get_average("Read"), 1000)
        self.estimator.record_actual("Read", 500)
        avg = self.estimator.get_average("Read")
        # EMA: 0.3 * 500 + 0.7 * 1000 = 850
        self.assertEqual(avg, 850)

    def test_is_affordable_true(self):
        self.assertTrue(self.estimator.is_affordable("Read", 10000))

    def test_is_affordable_false(self):
        self.estimator.record_actual("BigTool", 50000)
        self.assertFalse(self.estimator.is_affordable("BigTool", 100))

    def test_within_budget_flag(self):
        est = self.estimator.estimate("Bash", budget_remaining=10)
        self.assertFalse(est.within_budget)

    def test_summary(self):
        text = self.estimator.summary()
        self.assertIn("PreCallEstimator", text)
        self.assertIn("no history", text)


if __name__ == "__main__":
    unittest.main()
