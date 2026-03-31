"""Tests for Q169 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q169_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ169Commands(unittest.TestCase):
    def setUp(self):
        q169_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q169_cmds.register(MockRegistry())

    def test_commands_registered(self):
        self.assertIn("agent-run", self.registered)
        self.assertIn("agent-status", self.registered)
        self.assertIn("agent-list", self.registered)
        self.assertIn("agent-cancel", self.registered)

    # --- /agent-run ---

    def test_agent_run_no_args(self):
        result = _run(self.registered["agent-run"].handler(""))
        self.assertIn("Usage", result)

    def test_agent_run_submit(self):
        result = _run(self.registered["agent-run"].handler("fix the bug"))
        self.assertIn("Agent submitted", result)

    # --- /agent-status ---

    def test_agent_status_pool_summary(self):
        result = _run(self.registered["agent-status"].handler(""))
        self.assertIn("Pool", result)

    def test_agent_status_specific(self):
        run_result = _run(self.registered["agent-run"].handler("fix"))
        agent_id = run_result.split(": ")[1].strip()
        result = _run(self.registered["agent-status"].handler(agent_id))
        self.assertIn(agent_id, result)
        self.assertIn("fix", result)

    def test_agent_status_unknown(self):
        result = _run(self.registered["agent-status"].handler("nonexistent"))
        self.assertIn("Unknown", result)

    # --- /agent-list ---

    def test_agent_list_empty(self):
        result = _run(self.registered["agent-list"].handler(""))
        self.assertIn("No agents", result)

    def test_agent_list_with_agents(self):
        _run(self.registered["agent-run"].handler("task one"))
        _run(self.registered["agent-run"].handler("task two"))
        result = _run(self.registered["agent-list"].handler(""))
        self.assertIn("Agents (2)", result)

    # --- /agent-cancel ---

    def test_agent_cancel_no_args(self):
        result = _run(self.registered["agent-cancel"].handler(""))
        self.assertIn("Usage", result)

    def test_agent_cancel_success(self):
        run_result = _run(self.registered["agent-run"].handler("do stuff"))
        agent_id = run_result.split(": ")[1].strip()
        result = _run(self.registered["agent-cancel"].handler(agent_id))
        self.assertIn("cancelled", result)

    def test_agent_cancel_nonexistent(self):
        result = _run(self.registered["agent-cancel"].handler("nope"))
        self.assertIn("Cannot cancel", result)


if __name__ == "__main__":
    unittest.main()
