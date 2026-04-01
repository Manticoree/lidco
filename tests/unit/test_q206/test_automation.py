"""Tests for computer_use.automation."""
from __future__ import annotations

import unittest

from lidco.computer_use.automation import AutomationAction, AutomationRunner, AutomationScript
from lidco.computer_use.controller import ScreenController


class TestRecordAction(unittest.TestCase):
    def setUp(self):
        self.runner = AutomationRunner()

    def test_record_action_returns_action(self):
        action = self.runner.record_action("click", {"x": 10, "y": 20})
        self.assertEqual(action.action_type, "click")
        self.assertEqual(action.params["x"], 10)

    def test_record_action_with_description(self):
        action = self.runner.record_action("click", {"x": 1, "y": 2}, description="Click button")
        self.assertEqual(action.description, "Click button")

    def test_record_action_default_params(self):
        action = self.runner.record_action("move")
        self.assertEqual(action.params, {})

    def test_recorded_actions_list(self):
        self.runner.record_action("click", {"x": 1, "y": 2})
        self.runner.record_action("type_text", {"text": "hi"})
        actions = self.runner.recorded_actions()
        self.assertEqual(len(actions), 2)


class TestCreateScript(unittest.TestCase):
    def test_create_script_captures_actions(self):
        runner = AutomationRunner()
        runner.record_action("click", {"x": 5, "y": 5})
        runner.record_action("type_text", {"text": "hello"})
        script = runner.create_script("my_script")
        self.assertEqual(script.name, "my_script")
        self.assertEqual(len(script.actions), 2)
        self.assertGreater(script.created_at, 0)


class TestReplay(unittest.TestCase):
    def test_replay_click(self):
        ctrl = ScreenController()
        runner = AutomationRunner(controller=ctrl)
        action = AutomationAction(action_type="click", params={"x": 50, "y": 60})
        script = AutomationScript(name="test", actions=(action,))
        results = runner.replay(script)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "ok")
        self.assertEqual(results[0]["position"], (50, 60))

    def test_replay_type_text(self):
        runner = AutomationRunner()
        action = AutomationAction(action_type="type_text", params={"text": "hi"})
        script = AutomationScript(name="test", actions=(action,))
        results = runner.replay(script)
        self.assertEqual(results[0]["text"], "hi")

    def test_replay_unknown_action(self):
        runner = AutomationRunner()
        action = AutomationAction(action_type="unknown_thing", params={})
        script = AutomationScript(name="test", actions=(action,))
        results = runner.replay(script)
        self.assertEqual(results[0]["status"], "unknown_action")

    def test_replay_hotkey(self):
        runner = AutomationRunner()
        action = AutomationAction(action_type="hotkey", params={"keys": ["ctrl", "c"]})
        script = AutomationScript(name="test", actions=(action,))
        results = runner.replay(script)
        self.assertEqual(results[0]["combo"], "ctrl+c")


class TestClearRecording(unittest.TestCase):
    def test_clear(self):
        runner = AutomationRunner()
        runner.record_action("click", {"x": 1, "y": 2})
        runner.clear_recording()
        self.assertEqual(len(runner.recorded_actions()), 0)


if __name__ == "__main__":
    unittest.main()
