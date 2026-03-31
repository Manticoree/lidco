"""Tests for HintEngine."""
from __future__ import annotations

import unittest

from lidco.flow.action_tracker import ActionTracker
from lidco.flow.intent_inferrer import IntentInferrer
from lidco.flow.hint_engine import HintEngine, Hint


class TestHintDataclass(unittest.TestCase):
    def test_fields(self):
        h = Hint(text="Do X", category="debug", priority=2)
        self.assertEqual(h.text, "Do X")
        self.assertEqual(h.category, "debug")
        self.assertEqual(h.priority, 2)
        self.assertIsNone(h.action_suggestion)

    def test_with_action_suggestion(self):
        h = Hint(text="Run tests", category="testing", priority=1, action_suggestion="pytest")
        self.assertEqual(h.action_suggestion, "pytest")


class TestGenerateHintsEmpty(unittest.TestCase):
    def test_no_actions_returns_exploring_hints(self):
        t = ActionTracker()
        inf = IntentInferrer(t)
        engine = HintEngine(t, inf)
        hints = engine.generate_hints()
        # Even with no actions, exploring hints should be available
        self.assertIsInstance(hints, list)


class TestGenerateHintsDebugging(unittest.TestCase):
    def test_debugging_hints(self):
        t = ActionTracker()
        for _ in range(20):
            t.track("error", "fail", success=False)
        inf = IntentInferrer(t)
        engine = HintEngine(t, inf)
        hints = engine.generate_hints()
        self.assertTrue(len(hints) > 0)
        categories = {h.category for h in hints}
        self.assertTrue("error_rate" in categories or "debugging" in categories)


class TestGenerateHintsHighErrorRate(unittest.TestCase):
    def test_high_error_rate_warning(self):
        t = ActionTracker()
        for _ in range(30):
            t.track("error", "fail", success=False)
        inf = IntentInferrer(t)
        engine = HintEngine(t, inf)
        hints = engine.generate_hints()
        error_hints = [h for h in hints if h.category == "error_rate"]
        self.assertTrue(len(error_hints) > 0)
        self.assertIn("failed", error_hints[0].text)


class TestGenerateHintsMaxLimit(unittest.TestCase):
    def test_max_hints_respected(self):
        t = ActionTracker()
        for _ in range(10):
            t.track("edit", "e", file_path="/a.py")
        inf = IntentInferrer(t)
        engine = HintEngine(t, inf)
        hints = engine.generate_hints(max_hints=1)
        self.assertLessEqual(len(hints), 1)


class TestGenerateHintsPrioritySorted(unittest.TestCase):
    def test_hints_sorted_by_priority(self):
        t = ActionTracker()
        for _ in range(10):
            t.track("edit", "create new_thing.py", file_path="/new.py")
        inf = IntentInferrer(t)
        engine = HintEngine(t, inf)
        hints = engine.generate_hints(max_hints=5)
        if len(hints) > 1:
            priorities = [h.priority for h in hints]
            self.assertEqual(priorities, sorted(priorities))


class TestDismiss(unittest.TestCase):
    def test_dismiss_removes_hint(self):
        t = ActionTracker()
        for _ in range(10):
            t.track("edit", "create new_thing.py", file_path="/new.py")
        inf = IntentInferrer(t)
        engine = HintEngine(t, inf)
        hints = engine.generate_hints()
        if hints:
            first_text = hints[0].text
            engine.dismiss(first_text)
            hints2 = engine.generate_hints()
            texts = {h.text for h in hints2}
            self.assertNotIn(first_text, texts)

    def test_dismiss_multiple(self):
        t = ActionTracker()
        for _ in range(10):
            t.track("edit", "e", file_path="/a.py")
        inf = IntentInferrer(t)
        engine = HintEngine(t, inf)
        hints = engine.generate_hints(max_hints=5)
        for h in hints:
            engine.dismiss(h.text)
        self.assertEqual(len(engine.generate_hints(max_hints=5)), 0)


class TestHintsForDifferentIntents(unittest.TestCase):
    def test_testing_intent_hints(self):
        t = ActionTracker()
        for i in range(5):
            t.track("edit", f"edit{i}", file_path=f"/tests/test_{i}.py")
        for _ in range(5):
            t.track("command", "pytest")
        inf = IntentInferrer(t)
        engine = HintEngine(t, inf)
        hints = engine.generate_hints()
        self.assertTrue(len(hints) > 0)

    def test_reviewing_intent_hints(self):
        t = ActionTracker()
        for i in range(15):
            t.track("read", f"read{i}")
        for i in range(3):
            t.track("search", f"grep{i}")
        inf = IntentInferrer(t)
        engine = HintEngine(t, inf)
        hints = engine.generate_hints()
        self.assertTrue(len(hints) > 0)


if __name__ == "__main__":
    unittest.main()
