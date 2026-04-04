"""Tests for cot.planner."""
import unittest
from lidco.cot.planner import CoTPlanner, ReasoningStep, StepStatus


class TestCoTPlanner(unittest.TestCase):

    def setUp(self):
        self.planner = CoTPlanner()

    def test_add_step(self):
        s = self.planner.add_step("Analyze the problem")
        self.assertIsInstance(s, ReasoningStep)
        self.assertEqual(s.status, StepStatus.PENDING)

    def test_steps_order(self):
        self.planner.add_step("Step 1")
        self.planner.add_step("Step 2")
        steps = self.planner.steps()
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].description, "Step 1")

    def test_decompose_simple(self):
        steps = self.planner.decompose("What is recursion?")
        self.assertGreater(len(steps), 1)

    def test_decompose_multipart(self):
        steps = self.planner.decompose("What is recursion? How does it compare to iteration? When to use each?")
        self.assertGreater(len(steps), 2)

    def test_ready_steps(self):
        s1 = self.planner.add_step("First")
        s2 = self.planner.add_step("Second", depends_on=[s1.step_id])
        ready = self.planner.ready_steps()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].step_id, s1.step_id)

    def test_ready_after_completion(self):
        s1 = self.planner.add_step("First")
        s2 = self.planner.add_step("Second", depends_on=[s1.step_id])
        s1.status = StepStatus.COMPLETED
        ready = self.planner.ready_steps()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].step_id, s2.step_id)

    def test_get_step(self):
        s = self.planner.add_step("Test")
        self.assertEqual(self.planner.get_step(s.step_id).description, "Test")

    def test_get_step_missing(self):
        self.assertIsNone(self.planner.get_step("nonexistent"))

    def test_total_estimated_tokens(self):
        self.planner.add_step("S1", estimated_tokens=200)
        self.planner.add_step("S2", estimated_tokens=300)
        self.assertEqual(self.planner.total_estimated_tokens(), 500)

    def test_completion_pct(self):
        s1 = self.planner.add_step("S1")
        self.planner.add_step("S2")
        s1.status = StepStatus.COMPLETED
        self.assertEqual(self.planner.completion_pct(), 50.0)

    def test_completion_pct_empty(self):
        self.assertEqual(self.planner.completion_pct(), 0.0)

    def test_dependency_order(self):
        s1 = self.planner.add_step("S1")
        s2 = self.planner.add_step("S2", depends_on=[s1.step_id])
        order = self.planner.dependency_order()
        self.assertEqual(order.index(s1.step_id), 0)

    def test_summary(self):
        self.planner.add_step("S1")
        s = self.planner.summary()
        self.assertEqual(s["total_steps"], 1)
        self.assertEqual(s["pending"], 1)


if __name__ == "__main__":
    unittest.main()
