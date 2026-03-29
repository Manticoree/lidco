"""Tests for Q118 CLI commands (Task 726)."""
from __future__ import annotations

import asyncio
import json
import unittest

from lidco.cli.commands import q118_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ118Commands(unittest.TestCase):
    def setUp(self):
        # Reset module state between tests
        q118_cmds._state.clear()

        # Create a mock registry to capture registrations
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q118_cmds.register(MockRegistry())
        self.handler = self.registered["automation"].handler

    # -- usage --------------------------------------------------------------

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("foobar"))
        self.assertIn("Usage", result)

    # -- list ---------------------------------------------------------------

    def test_list_empty(self):
        result = _run(self.handler("list"))
        self.assertIn("No automation triggers", result)

    def test_list_after_add(self):
        _run(self.handler("add cron daily Run daily"))
        result = _run(self.handler("list"))
        self.assertIn("daily", result)
        self.assertIn("cron", result)
        self.assertIn("enabled", result)

    # -- add ----------------------------------------------------------------

    def test_add_basic(self):
        result = _run(self.handler("add webhook hook1 Process {{title}}"))
        self.assertIn("Registered", result)
        self.assertIn("hook1", result)

    def test_add_missing_args(self):
        result = _run(self.handler("add cron"))
        self.assertIn("Usage", result)

    def test_add_duplicate(self):
        _run(self.handler("add cron t1 template"))
        result = _run(self.handler("add cron t1 template2"))
        self.assertIn("already exists", result)

    def test_add_different_types(self):
        _run(self.handler("add cron c1 template1"))
        _run(self.handler("add slack s1 template2"))
        result = _run(self.handler("list"))
        self.assertIn("c1", result)
        self.assertIn("s1", result)

    # -- run ----------------------------------------------------------------

    def test_run_missing_name(self):
        result = _run(self.handler("run"))
        self.assertIn("Usage", result)

    def test_run_trigger_not_found(self):
        result = _run(self.handler("run nonexistent"))
        self.assertIn("not found", result)

    def test_run_basic(self):
        _run(self.handler("add cron daily Do stuff"))
        result = _run(self.handler("run daily"))
        self.assertIn("Ran", result)
        self.assertIn("1 trigger(s)", result)

    def test_run_with_payload(self):
        _run(self.handler("add github_pr pr_review Review {{title}}"))
        payload = json.dumps({"number": 1, "title": "Fix", "body": ""})
        result = _run(self.handler(f"run pr_review {payload}"))
        self.assertIn("Ran", result)

    def test_run_invalid_json(self):
        _run(self.handler("add cron daily Do stuff"))
        result = _run(self.handler("run daily {invalid"))
        self.assertIn("Invalid JSON", result)

    # -- history ------------------------------------------------------------

    def test_history_empty(self):
        result = _run(self.handler("history"))
        self.assertIn("No automation history", result)

    def test_history_after_run(self):
        _run(self.handler("add cron daily Do stuff"))
        _run(self.handler("run daily"))
        result = _run(self.handler("history"))
        self.assertIn("Recent", result)
        self.assertIn("daily", result)

    # -- enable / disable ---------------------------------------------------

    def test_enable_missing_name(self):
        result = _run(self.handler("enable"))
        self.assertIn("Usage", result)

    def test_disable_missing_name(self):
        result = _run(self.handler("disable"))
        self.assertIn("Usage", result)

    def test_enable_not_found(self):
        result = _run(self.handler("enable nope"))
        self.assertIn("not found", result)

    def test_disable_not_found(self):
        result = _run(self.handler("disable nope"))
        self.assertIn("not found", result)

    def test_disable_trigger(self):
        _run(self.handler("add cron daily template"))
        result = _run(self.handler("disable daily"))
        self.assertIn("Disabled", result)

    def test_enable_trigger(self):
        _run(self.handler("add cron daily template"))
        _run(self.handler("disable daily"))
        result = _run(self.handler("enable daily"))
        self.assertIn("Enabled", result)

    def test_disable_shows_in_list(self):
        _run(self.handler("add cron daily template"))
        _run(self.handler("disable daily"))
        result = _run(self.handler("list"))
        self.assertIn("disabled", result)

    # -- registration -------------------------------------------------------

    def test_command_registered(self):
        self.assertIn("automation", self.registered)

    def test_command_description(self):
        self.assertIn("Automations", self.registered["automation"].description)

    # -- with agent_fn ------------------------------------------------------

    def test_run_with_agent_fn(self):
        q118_cmds._state.clear()
        q118_cmds._state["agent_fn"] = lambda p: f"Agent says: {p[:10]}"

        class MockReg:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q118_cmds.register(MockReg())
        handler = self.registered["automation"].handler

        _run(handler("add cron t1 task"))
        result = _run(handler("run t1"))
        self.assertIn("Ran", result)


if __name__ == "__main__":
    unittest.main()
