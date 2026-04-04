"""Tests for cot.visualizer."""
import unittest
from lidco.cot.planner import ReasoningStep, StepStatus
from lidco.cot.visualizer import CoTVisualizer


class TestCoTVisualizer(unittest.TestCase):

    def setUp(self):
        self.viz = CoTVisualizer()

    def _steps(self):
        s1 = ReasoningStep(step_id="s1", description="Analyze")
        s2 = ReasoningStep(step_id="s2", description="Solve", depends_on=["s1"])
        s3 = ReasoningStep(step_id="s3", description="Verify", depends_on=["s2"])
        s1.status = StepStatus.COMPLETED
        return [s1, s2, s3]

    def test_text_tree(self):
        tree = self.viz.as_text_tree(self._steps())
        self.assertIn("s1", tree)
        self.assertIn("[x]", tree)  # completed

    def test_text_tree_empty(self):
        self.assertEqual(self.viz.as_text_tree([]), "(empty chain)")

    def test_mermaid(self):
        mermaid = self.viz.as_mermaid(self._steps())
        self.assertIn("graph TD", mermaid)
        self.assertIn("-->", mermaid)

    def test_mermaid_empty(self):
        result = self.viz.as_mermaid([])
        self.assertIn("No steps", result)

    def test_as_json(self):
        data = self.viz.as_json(self._steps())
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]["status"], "completed")

    def test_critical_path(self):
        steps = self._steps()
        path = self.viz.critical_path(steps)
        self.assertEqual(path, ["s1", "s2", "s3"])

    def test_critical_path_empty(self):
        self.assertEqual(self.viz.critical_path([]), [])

    def test_summary(self):
        s = self.viz.summary(self._steps())
        self.assertEqual(s["total_steps"], 3)
        self.assertEqual(s["completed"], 1)
        self.assertEqual(s["critical_path_length"], 3)

    def test_text_tree_with_failed(self):
        steps = self._steps()
        steps[1].status = StepStatus.FAILED
        tree = self.viz.as_text_tree(steps)
        self.assertIn("[!]", tree)


if __name__ == "__main__":
    unittest.main()
