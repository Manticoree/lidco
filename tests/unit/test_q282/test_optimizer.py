"""Tests for cot.optimizer."""
import unittest
from lidco.cot.planner import ReasoningStep
from lidco.cot.optimizer import CoTOptimizer


class TestCoTOptimizer(unittest.TestCase):

    def setUp(self):
        self.opt = CoTOptimizer()

    def _steps(self):
        return [
            ReasoningStep(step_id="s1", description="Analyze problem"),
            ReasoningStep(step_id="s2", description="Find solution", depends_on=["s1"]),
            ReasoningStep(step_id="s3", description="Verify answer", depends_on=["s1"]),
            ReasoningStep(step_id="s4", description="Analyze problem"),  # duplicate
        ]

    def test_find_redundant(self):
        steps = self._steps()
        redundant = self.opt.find_redundant(steps)
        self.assertIn("s4", redundant)

    def test_find_no_redundant(self):
        steps = self._steps()[:3]
        redundant = self.opt.find_redundant(steps)
        self.assertEqual(len(redundant), 0)

    def test_find_parallelizable(self):
        steps = self._steps()[:3]
        groups = self.opt.find_parallelizable(steps)
        # s2 and s3 both depend only on s1 -> parallelizable
        self.assertGreater(len(groups), 0)

    def test_optimize(self):
        steps = self._steps()
        result = self.opt.optimize(steps)
        self.assertEqual(result.original_steps, 4)
        self.assertEqual(result.optimized_steps, 3)
        self.assertIn("s4", result.removed_steps)

    def test_cache(self):
        self.opt.cache_result("Analyze problem", "It's a sorting issue")
        self.assertEqual(self.opt.get_cached("Analyze problem"), "It's a sorting issue")

    def test_cache_miss(self):
        self.assertIsNone(self.opt.get_cached("Unknown"))

    def test_cache_case_insensitive(self):
        self.opt.cache_result("Analyze Problem", "result")
        self.assertEqual(self.opt.get_cached("analyze problem"), "result")

    def test_cache_size(self):
        self.opt.cache_result("a", "1")
        self.opt.cache_result("b", "2")
        self.assertEqual(self.opt.cache_size(), 2)

    def test_clear_cache(self):
        self.opt.cache_result("a", "1")
        self.opt.clear_cache()
        self.assertEqual(self.opt.cache_size(), 0)

    def test_optimize_empty(self):
        result = self.opt.optimize([])
        self.assertEqual(result.original_steps, 0)


if __name__ == "__main__":
    unittest.main()
