"""Tests for cot.executor."""
import unittest
from lidco.cot.planner import ReasoningStep, StepStatus
from lidco.cot.executor import StepExecutor, StepCheckpoint


class TestStepExecutor(unittest.TestCase):

    def setUp(self):
        self.executor = StepExecutor()

    def _make_step(self, sid="s1", desc="Test step"):
        return ReasoningStep(step_id=sid, description=desc)

    def test_execute(self):
        step = self._make_step()
        result = self.executor.execute(step, "Answer found")
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.result, "Answer found")

    def test_fail(self):
        step = self._make_step()
        result = self.executor.fail(step, "Timeout")
        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertIn("Timeout", result.result)

    def test_skip(self):
        step = self._make_step()
        result = self.executor.skip(step, "Not needed")
        self.assertEqual(result.status, StepStatus.SKIPPED)

    def test_get_result(self):
        step = self._make_step()
        self.executor.execute(step, "Result")
        self.assertEqual(self.executor.get_result("s1"), "Result")

    def test_get_result_missing(self):
        self.assertIsNone(self.executor.get_result("nope"))

    def test_checkpoints(self):
        step = self._make_step()
        self.executor.execute(step, "Result")
        cps = self.executor.checkpoints()
        self.assertEqual(len(cps), 1)

    def test_checkpoint_for(self):
        step = self._make_step()
        self.executor.execute(step, "Result")
        cp = self.executor.checkpoint_for("s1")
        self.assertIsNotNone(cp)
        self.assertEqual(cp.intermediate_result, "Result")

    def test_checkpoint_for_missing(self):
        self.assertIsNone(self.executor.checkpoint_for("nope"))

    def test_resume_from(self):
        step = self._make_step()
        self.executor.execute(step, "Partial")
        cp = self.executor.resume_from("s1")
        self.assertIsNotNone(cp)

    def test_execution_log(self):
        step = self._make_step()
        self.executor.execute(step, "Done")
        log = self.executor.execution_log()
        self.assertEqual(len(log), 2)  # start + complete

    def test_summary(self):
        step = self._make_step()
        self.executor.execute(step, "Done")
        s = self.executor.summary()
        self.assertEqual(s["executed"], 1)


if __name__ == "__main__":
    unittest.main()
