"""Tests for cli.commands.q228_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class TestQ228Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q228_cmds

        q228_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"auto-compact", "compaction-log", "compact-tools", "compaction-config"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_auto_compact_usage(self):
        handler = self.registered["auto-compact"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_auto_compact_no_action(self):
        handler = self.registered["auto-compact"].handler
        result = asyncio.run(handler("0.3"))
        self.assertIn("no compaction", result)

    def test_auto_compact_triggers(self):
        handler = self.registered["auto-compact"].handler
        result = asyncio.run(handler("0.96"))
        self.assertIn("emergency", result)

    def test_auto_compact_bad_input(self):
        handler = self.registered["auto-compact"].handler
        result = asyncio.run(handler("abc"))
        self.assertIn("Error", result)

    def test_compaction_log_empty(self):
        handler = self.registered["compaction-log"].handler
        result = asyncio.run(handler(""))
        self.assertIn("empty", result)

    def test_compact_tools_summary(self):
        handler = self.registered["compact-tools"].handler
        result = asyncio.run(handler(""))
        self.assertIn("ToolCompressor", result)

    def test_compaction_config_summary(self):
        handler = self.registered["compaction-config"].handler
        result = asyncio.run(handler(""))
        self.assertIn("StrategySelector", result)

    def test_compaction_config_with_util(self):
        handler = self.registered["compaction-config"].handler
        result = asyncio.run(handler("0.95"))
        self.assertIn("critical", result)


if __name__ == "__main__":
    unittest.main()
