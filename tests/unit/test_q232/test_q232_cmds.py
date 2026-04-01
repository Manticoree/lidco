"""Tests for cli.commands.q232_cmds — /tool-budget, /tool-stats, /truncation-config, /result-limits."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class TestQ232Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q232_cmds

        q232_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"tool-budget", "tool-stats", "truncation-config", "result-limits"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_tool_budget_default(self):
        handler = self.registered["tool-budget"].handler
        result = asyncio.run(handler(""))
        self.assertIn("ToolBudgetGate", result)
        self.assertIn("100000", result)

    def test_tool_budget_custom(self):
        handler = self.registered["tool-budget"].handler
        result = asyncio.run(handler("50000 3000"))
        self.assertIn("50000", result)
        self.assertIn("3000", result)

    def test_tool_stats_usage(self):
        handler = self.registered["tool-stats"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_tool_stats_with_args(self):
        handler = self.registered["tool-stats"].handler
        result = asyncio.run(handler("Read 500 300"))
        self.assertIn("Read", result)
        self.assertIn("800", result)

    def test_truncation_config_default(self):
        handler = self.registered["truncation-config"].handler
        result = asyncio.run(handler(""))
        self.assertIn("AdaptiveTruncator", result)

    def test_truncation_config_set(self):
        handler = self.registered["truncation-config"].handler
        result = asyncio.run(handler("Read 800"))
        self.assertIn("Read=800", result)

    def test_result_limits(self):
        handler = self.registered["result-limits"].handler
        result = asyncio.run(handler(""))
        self.assertIn("ResultLimiter", result)
        self.assertIn("Read", result)


if __name__ == "__main__":
    unittest.main()
