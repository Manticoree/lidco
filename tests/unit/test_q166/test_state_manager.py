"""Tests for FlowStateManager."""
from __future__ import annotations

import time
import unittest

from lidco.flow.action_tracker import ActionTracker
from lidco.flow.intent_inferrer import IntentInferrer
from lidco.flow.state_manager import FlowStateManager, FlowState


class TestFlowState(unittest.TestCase):
    def test_dataclass_fields(self):
        fs = FlowState(session_start=1.0, total_actions=10, current_intent="debugging")
        self.assertEqual(fs.session_start, 1.0)
        self.assertEqual(fs.total_actions, 10)
        self.assertEqual(fs.current_intent, "debugging")
        self.assertEqual(fs.intent_history, [])
        self.assertAlmostEqual(fs.productivity_score, 100.0)


class TestUpdate(unittest.TestCase):
    def test_update_returns_flow_state(self):
        t = ActionTracker()
        inf = IntentInferrer(t)
        mgr = FlowStateManager(t, inf)
        state = mgr.update()
        self.assertIsInstance(state, FlowState)

    def test_update_tracks_actions(self):
        t = ActionTracker()
        t.track("edit", "e1")
        t.track("edit", "e2")
        inf = IntentInferrer(t)
        mgr = FlowStateManager(t, inf)
        state = mgr.update()
        self.assertEqual(state.total_actions, 2)


class TestProductivityScore(unittest.TestCase):
    def test_all_success(self):
        t = ActionTracker()
        for _ in range(10):
            t.track("edit", "ok")
        mgr = FlowStateManager(t, IntentInferrer(t))
        self.assertAlmostEqual(mgr.productivity_score(), 100.0)

    def test_half_fail(self):
        t = ActionTracker()
        for _ in range(5):
            t.track("edit", "ok")
        for _ in range(5):
            t.track("error", "fail", success=False)
        mgr = FlowStateManager(t, IntentInferrer(t))
        self.assertAlmostEqual(mgr.productivity_score(), 50.0)

    def test_no_actions(self):
        t = ActionTracker()
        mgr = FlowStateManager(t, IntentInferrer(t))
        self.assertAlmostEqual(mgr.productivity_score(), 100.0)


class TestSessionDuration(unittest.TestCase):
    def test_duration_positive(self):
        t = ActionTracker()
        mgr = FlowStateManager(t, IntentInferrer(t))
        dur = mgr.session_duration()
        self.assertGreaterEqual(dur, 0.0)


class TestIntentSwitches(unittest.TestCase):
    def test_no_switches_initially(self):
        t = ActionTracker()
        mgr = FlowStateManager(t, IntentInferrer(t))
        self.assertEqual(mgr.intent_switches(), 0)

    def test_switches_count(self):
        t = ActionTracker()
        inf = IntentInferrer(t)
        mgr = FlowStateManager(t, inf)

        # First update -> exploring
        mgr.update()

        # Add errors -> debugging
        for _ in range(20):
            t.track("error", "err", success=False)
        mgr.update()

        # Clear and add edits -> refactoring
        t.clear()
        for _ in range(15):
            t.track("edit", "edit", file_path="/a.py")
        mgr.update()

        self.assertGreaterEqual(mgr.intent_switches(), 1)


class TestExportImport(unittest.TestCase):
    def test_export_returns_dict(self):
        t = ActionTracker()
        t.track("edit", "e1")
        mgr = FlowStateManager(t, IntentInferrer(t))
        data = mgr.export()
        self.assertIsInstance(data, dict)
        self.assertIn("session_start", data)
        self.assertIn("total_actions", data)
        self.assertIn("current_intent", data)
        self.assertIn("productivity_score", data)
        self.assertIn("session_duration", data)
        self.assertIn("intent_switches", data)

    def test_import_restores_state(self):
        t = ActionTracker()
        mgr = FlowStateManager(t, IntentInferrer(t))
        data = {
            "session_start": 100.0,
            "intent_history": [(100.0, "debugging"), (110.0, "refactoring")],
        }
        mgr.import_state(data)
        self.assertEqual(mgr._session_start, 100.0)
        self.assertEqual(len(mgr._intent_history), 2)
        self.assertEqual(mgr._last_intent, "refactoring")


class TestSummary(unittest.TestCase):
    def test_summary_returns_string(self):
        t = ActionTracker()
        t.track("edit", "e1")
        mgr = FlowStateManager(t, IntentInferrer(t))
        s = mgr.summary()
        self.assertIsInstance(s, str)
        self.assertIn("Session:", s)
        self.assertIn("Actions:", s)
        self.assertIn("Intent:", s)
        self.assertIn("Productivity:", s)


if __name__ == "__main__":
    unittest.main()
