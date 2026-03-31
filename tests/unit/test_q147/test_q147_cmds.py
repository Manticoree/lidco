"""Tests for Q147 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest

from lidco.cli.commands import q147_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ147Commands(unittest.TestCase):
    def setUp(self):
        q147_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q147_cmds.register(MockRegistry())

    # ------------------------------------------------------------------ registration

    def test_commands_registered(self):
        self.assertIn("notify", self.registered)
        self.assertIn("toast", self.registered)
        self.assertIn("alert", self.registered)

    # ------------------------------------------------------------------ /notify

    def test_notify_no_args(self):
        result = _run(self.registered["notify"].handler(""))
        self.assertIn("Usage", result)

    def test_notify_push(self):
        result = _run(self.registered["notify"].handler("push info Test | Hello world"))
        self.assertIn("pushed", result.lower())
        self.assertIn("INFO", result)

    def test_notify_push_no_message(self):
        result = _run(self.registered["notify"].handler("push info Title only"))
        self.assertIn("pushed", result.lower())

    def test_notify_push_invalid_level(self):
        result = _run(self.registered["notify"].handler("push critical Bad | Msg"))
        self.assertIn("Invalid", result)

    def test_notify_push_missing_args(self):
        result = _run(self.registered["notify"].handler("push info"))
        self.assertIn("Usage", result)

    def test_notify_list_empty(self):
        result = _run(self.registered["notify"].handler("list"))
        self.assertIn("No notifications", result)

    def test_notify_list_populated(self):
        _run(self.registered["notify"].handler("push info Hello | World"))
        result = _run(self.registered["notify"].handler("list"))
        self.assertIn("unread", result)
        self.assertIn("Hello", result)

    def test_notify_read(self):
        _run(self.registered["notify"].handler("push info Title | Body"))
        result = _run(self.registered["notify"].handler("read"))
        self.assertIn("Title", result)
        self.assertIn("Body", result)

    def test_notify_read_empty(self):
        result = _run(self.registered["notify"].handler("read"))
        self.assertIn("No unread", result)

    def test_notify_clear(self):
        _run(self.registered["notify"].handler("push info A | B"))
        _run(self.registered["notify"].handler("read"))  # mark as read
        result = _run(self.registered["notify"].handler("clear"))
        self.assertIn("cleared", result.lower())

    def test_notify_unknown_sub(self):
        result = _run(self.registered["notify"].handler("zzz"))
        self.assertIn("Usage", result)

    # ------------------------------------------------------------------ /toast

    def test_toast_no_args(self):
        result = _run(self.registered["toast"].handler(""))
        self.assertIn("Usage", result)

    def test_toast_show(self):
        result = _run(self.registered["toast"].handler("show Hello toast"))
        self.assertIn("[INFO]", result)
        self.assertIn("Hello toast", result)

    def test_toast_show_empty_message(self):
        result = _run(self.registered["toast"].handler("show"))
        self.assertIn("Usage", result)

    def test_toast_active(self):
        _run(self.registered["toast"].handler("show First"))
        result = _run(self.registered["toast"].handler("active"))
        self.assertIn("Active toasts", result)
        self.assertIn("First", result)

    def test_toast_active_empty(self):
        result = _run(self.registered["toast"].handler("active"))
        self.assertIn("No active", result)

    def test_toast_dismiss_all(self):
        _run(self.registered["toast"].handler("show Msg"))
        result = _run(self.registered["toast"].handler("dismiss"))
        self.assertIn("dismissed", result.lower())

    def test_toast_dismiss_by_index(self):
        _run(self.registered["toast"].handler("show A"))
        result = _run(self.registered["toast"].handler("dismiss 0"))
        self.assertIn("dismissed", result.lower())

    def test_toast_dismiss_invalid_index(self):
        result = _run(self.registered["toast"].handler("dismiss 99"))
        self.assertIn("No active toast", result)

    def test_toast_dismiss_bad_index(self):
        result = _run(self.registered["toast"].handler("dismiss abc"))
        self.assertIn("Usage", result)

    # ------------------------------------------------------------------ /alert

    def test_alert_no_args(self):
        result = _run(self.registered["alert"].handler(""))
        self.assertIn("Usage", result)

    def test_alert_add(self):
        result = _run(self.registered["alert"].handler("add myrule notify Hello"))
        self.assertIn("added", result.lower())
        self.assertIn("myrule", result)

    def test_alert_add_missing_args(self):
        result = _run(self.registered["alert"].handler("add myrule"))
        self.assertIn("Usage", result)

    def test_alert_list_empty(self):
        result = _run(self.registered["alert"].handler("list"))
        self.assertIn("No alert rules", result)

    def test_alert_list_populated(self):
        _run(self.registered["alert"].handler("add r1 notify tmpl"))
        result = _run(self.registered["alert"].handler("list"))
        self.assertIn("r1", result)
        self.assertIn("notify", result)

    def test_alert_eval_empty(self):
        result = _run(self.registered["alert"].handler("eval"))
        self.assertIn("No rules triggered", result)

    def test_alert_eval_triggered(self):
        _run(self.registered["alert"].handler("add r1 warn msg"))
        result = _run(self.registered["alert"].handler("eval {}"))
        self.assertIn("Triggered", result)

    def test_alert_eval_invalid_json(self):
        result = _run(self.registered["alert"].handler("eval {bad"))
        self.assertIn("Invalid JSON", result)

    def test_alert_unknown_sub(self):
        result = _run(self.registered["alert"].handler("zzz"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
