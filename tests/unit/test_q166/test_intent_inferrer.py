"""Tests for IntentInferrer."""
from __future__ import annotations

import unittest

from lidco.flow.action_tracker import ActionTracker
from lidco.flow.intent_inferrer import IntentInferrer, InferredIntent


class TestInferredIntent(unittest.TestCase):
    def test_dataclass_fields(self):
        i = InferredIntent(intent="debugging", confidence=0.8, evidence=["high errors"])
        self.assertEqual(i.intent, "debugging")
        self.assertAlmostEqual(i.confidence, 0.8)
        self.assertEqual(i.evidence, ["high errors"])

    def test_default_evidence(self):
        i = InferredIntent(intent="exploring", confidence=0.1)
        self.assertEqual(i.evidence, [])


class TestInferEmpty(unittest.TestCase):
    def test_no_actions_returns_exploring(self):
        t = ActionTracker()
        inf = IntentInferrer(t)
        result = inf.infer()
        self.assertEqual(result.intent, "exploring")
        self.assertLess(result.confidence, 0.5)


class TestInferDebugging(unittest.TestCase):
    def test_many_errors_infers_debugging(self):
        t = ActionTracker()
        for i in range(15):
            t.track("error", f"err{i}", success=False)
        for i in range(10):
            t.track("read", f"read{i}")
        inf = IntentInferrer(t)
        result = inf.infer()
        self.assertEqual(result.intent, "debugging")
        self.assertGreater(result.confidence, 0.3)


class TestInferRefactoring(unittest.TestCase):
    def test_many_edits_same_file(self):
        t = ActionTracker()
        for i in range(10):
            t.track("edit", f"edit{i}", file_path="/main.py")
        inf = IntentInferrer(t)
        result = inf.infer()
        self.assertEqual(result.intent, "refactoring")
        self.assertGreater(result.confidence, 0.3)


class TestInferFeatureDev(unittest.TestCase):
    def test_new_creates_and_edits(self):
        t = ActionTracker()
        for i in range(5):
            t.track("edit", f"create new_file_{i}.py", file_path=f"/new_{i}.py")
        for i in range(5):
            t.track("edit", f"edit{i}", file_path=f"/new_{i}.py")
        inf = IntentInferrer(t)
        result = inf.infer()
        self.assertEqual(result.intent, "feature_dev")


class TestInferTesting(unittest.TestCase):
    def test_test_file_edits_and_commands(self):
        t = ActionTracker()
        for i in range(5):
            t.track("edit", f"edit{i}", file_path=f"/tests/test_foo{i}.py")
        for i in range(5):
            t.track("command", "pytest")
        inf = IntentInferrer(t)
        result = inf.infer()
        self.assertEqual(result.intent, "testing")


class TestInferReviewingExploring(unittest.TestCase):
    def test_mostly_reads_with_search(self):
        t = ActionTracker()
        for i in range(15):
            t.track("read", f"read{i}", file_path=f"/src/{i}.py")
        for i in range(5):
            t.track("search", f"grep{i}")
        inf = IntentInferrer(t)
        result = inf.infer()
        self.assertEqual(result.intent, "reviewing")

    def test_mostly_reads_no_search(self):
        t = ActionTracker()
        for i in range(20):
            t.track("read", f"read{i}", file_path=f"/src/{i}.py")
        inf = IntentInferrer(t)
        result = inf.infer()
        self.assertEqual(result.intent, "exploring")


class TestExplain(unittest.TestCase):
    def test_explain_returns_string(self):
        t = ActionTracker()
        inf = IntentInferrer(t)
        explanation = inf.explain()
        self.assertIsInstance(explanation, str)
        self.assertIn("intent", explanation.lower())

    def test_explain_includes_intent(self):
        t = ActionTracker()
        for _ in range(10):
            t.track("error", "err", success=False)
        inf = IntentInferrer(t)
        explanation = inf.explain()
        self.assertIn("debugging", explanation)


if __name__ == "__main__":
    unittest.main()
