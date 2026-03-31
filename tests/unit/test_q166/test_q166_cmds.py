"""Tests for Q166 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q166_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ166Commands(unittest.TestCase):
    def setUp(self):
        q166_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q166_cmds.register(MockRegistry())

    def test_flow_registered(self):
        self.assertIn("flow", self.registered)

    def test_intent_registered(self):
        self.assertIn("intent", self.registered)

    # --- /flow ---

    def test_flow_status_default(self):
        handler = self.registered["flow"].handler
        result = _run(handler(""))
        self.assertIn("Session:", result)
        self.assertIn("Intent:", result)

    def test_flow_status_explicit(self):
        handler = self.registered["flow"].handler
        result = _run(handler("status"))
        self.assertIn("Session:", result)

    def test_flow_history_empty(self):
        handler = self.registered["flow"].handler
        result = _run(handler("history"))
        self.assertIn("No actions", result)

    def test_flow_hints(self):
        handler = self.registered["flow"].handler
        result = _run(handler("hints"))
        self.assertIsInstance(result, str)

    def test_flow_clear(self):
        handler = self.registered["flow"].handler
        result = _run(handler("clear"))
        self.assertIn("cleared", result.lower())

    def test_flow_stats_empty(self):
        handler = self.registered["flow"].handler
        result = _run(handler("stats"))
        self.assertIn("No actions", result)

    def test_flow_unknown_subcommand(self):
        handler = self.registered["flow"].handler
        result = _run(handler("zzz"))
        self.assertIn("Usage", result)

    # --- /intent ---

    def test_intent_output(self):
        handler = self.registered["intent"].handler
        result = _run(handler(""))
        self.assertIn("intent", result.lower())

    # --- flow with data ---

    def test_flow_history_with_data(self):
        # Access tracker through state and add data
        handler = self.registered["flow"].handler
        _run(handler("status"))  # initializes state
        tracker = q166_cmds._state["tracker"]
        tracker.track("edit", "changed main.py", file_path="/main.py")
        tracker.track("error", "syntax error", success=False)
        result = _run(handler("history"))
        self.assertIn("edit", result)
        self.assertIn("error", result)

    def test_flow_stats_with_data(self):
        handler = self.registered["flow"].handler
        _run(handler("status"))
        tracker = q166_cmds._state["tracker"]
        tracker.track("edit", "e1")
        tracker.track("read", "r1")
        result = _run(handler("stats"))
        self.assertIn("edit", result)
        self.assertIn("read", result)

    def test_flow_history_custom_limit(self):
        handler = self.registered["flow"].handler
        _run(handler("status"))
        tracker = q166_cmds._state["tracker"]
        for i in range(10):
            tracker.track("edit", f"op{i}")
        result = _run(handler("history 3"))
        self.assertIn("3", result)

    def test_flow_hints_with_errors(self):
        handler = self.registered["flow"].handler
        _run(handler("status"))
        tracker = q166_cmds._state["tracker"]
        for _ in range(30):
            tracker.track("error", "fail", success=False)
        result = _run(handler("hints"))
        self.assertIn("failed", result)


if __name__ == "__main__":
    unittest.main()
