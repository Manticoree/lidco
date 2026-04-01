"""Tests for cli.commands.q219_cmds — /compact, /compact-stats, /compact-preview, /context-budget."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class TestQ219Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q219_cmds

        q219_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"compact", "compact-stats", "compact-preview", "context-budget"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_all_commands_have_descriptions(self):
        for name, cmd in self.registered.items():
            self.assertIsInstance(cmd.description, str)
            self.assertTrue(len(cmd.description) > 0)

    def test_compact_default(self):
        handler = self.registered["compact"].handler
        result = asyncio.run(handler(""))
        self.assertIn("balanced", result.lower())

    def test_compact_aggressive(self):
        handler = self.registered["compact"].handler
        result = asyncio.run(handler("aggressive"))
        self.assertIn("aggressive", result.lower())

    def test_compact_unknown_strategy(self):
        handler = self.registered["compact"].handler
        result = asyncio.run(handler("unknown"))
        self.assertIn("Unknown strategy", result)

    def test_compact_stats(self):
        handler = self.registered["compact-stats"].handler
        result = asyncio.run(handler(""))
        self.assertIn("original_tokens", result)
        self.assertIn("max_ratio", result)

    def test_compact_preview(self):
        handler = self.registered["compact-preview"].handler
        result = asyncio.run(handler("500"))
        self.assertIn("Compacted", result)
        self.assertIn("Watermark", result)

    def test_context_budget(self):
        handler = self.registered["context-budget"].handler
        result = asyncio.run(handler("8000"))
        self.assertIn("8000", result)


if __name__ == "__main__":
    unittest.main()
