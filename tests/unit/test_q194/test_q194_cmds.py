"""Tests for cli.commands.q194_cmds — /cost-track, /cost-dashboard, /budget-hook, /cost-project."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class TestQ194Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q194_cmds

        q194_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"cost-track", "cost-dashboard", "budget-hook", "cost-project"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_cost_track_empty(self):
        handler = self.registered["cost-track"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Total cost", result)

    def test_cost_track_record(self):
        handler = self.registered["cost-track"].handler
        result = asyncio.run(handler("record gpt-4 1000 500"))
        self.assertIn("Recorded", result)
        self.assertIn("gpt-4", result)

    def test_cost_track_by_model(self):
        handler = self.registered["cost-track"].handler
        asyncio.run(handler("record gpt-4 1000 500"))
        result = asyncio.run(handler("by-model"))
        self.assertIn("gpt-4", result)

    def test_cost_track_usage(self):
        handler = self.registered["cost-track"].handler
        result = asyncio.run(handler("unknown-sub"))
        self.assertIn("Usage", result)

    def test_cost_dashboard_no_data(self):
        # Use a fresh registry to avoid stale state
        registry2 = MagicMock()
        registered2 = {}
        registry2.register = lambda cmd: registered2.__setitem__(cmd.name, cmd)
        from lidco.cli.commands import q194_cmds
        q194_cmds.register(registry2)
        handler = registered2["cost-dashboard"].handler
        result = asyncio.run(handler(""))
        self.assertIn("No cost data", result)

    def test_budget_hook_set(self):
        handler = self.registered["budget-hook"].handler
        result = asyncio.run(handler("set 0.5 1.0 session"))
        self.assertIn("Budget set", result)

    def test_budget_hook_check(self):
        handler = self.registered["budget-hook"].handler
        asyncio.run(handler("set 0.5 1.0 session"))
        result = asyncio.run(handler("check"))
        self.assertIn("Allowed", result)

    def test_budget_hook_usage(self):
        handler = self.registered["budget-hook"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_cost_project_with_data(self):
        track = self.registered["cost-track"].handler
        asyncio.run(track("record gpt-4 1000 500"))
        handler = self.registered["cost-project"].handler
        result = asyncio.run(handler("5"))
        self.assertIn("Projected total", result)
        self.assertIn("Trend", result)

    def test_cost_project_no_data(self):
        # Fresh registry
        registry2 = MagicMock()
        registered2 = {}
        registry2.register = lambda cmd: registered2.__setitem__(cmd.name, cmd)
        from lidco.cli.commands import q194_cmds
        q194_cmds.register(registry2)
        handler = registered2["cost-project"].handler
        result = asyncio.run(handler(""))
        self.assertIn("No cost data", result)

    def test_cost_track_has_description(self):
        cmd = self.registered["cost-track"]
        self.assertIsInstance(cmd.description, str)
        self.assertTrue(len(cmd.description) > 0)

    def test_all_commands_have_handlers(self):
        for name, cmd in self.registered.items():
            self.assertTrue(callable(cmd.handler), f"{name} has no handler")

    def test_cost_dashboard_after_record(self):
        track = self.registered["cost-track"].handler
        asyncio.run(track("record gpt-4 1000 500"))
        handler = self.registered["cost-dashboard"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Session total", result)

    def test_budget_hook_check_no_config(self):
        # Fresh registry
        registry2 = MagicMock()
        registered2 = {}
        registry2.register = lambda cmd: registered2.__setitem__(cmd.name, cmd)
        from lidco.cli.commands import q194_cmds
        q194_cmds.register(registry2)
        handler = registered2["budget-hook"].handler
        result = asyncio.run(handler("check"))
        self.assertIn("No budget configured", result)


if __name__ == "__main__":
    unittest.main()
