"""Tests for cli.commands.q195_cmds — /cache-stats, /cache-warm, /cache-clear, /token-optimize."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class TestQ195Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q195_cmds

        q195_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"cache-stats", "cache-warm", "cache-clear", "token-optimize"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_cache_stats_empty(self):
        handler = self.registered["cache-stats"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Hits:", result)
        self.assertIn("Size:", result)

    def test_cache_warm(self):
        handler = self.registered["cache-warm"].handler
        result = asyncio.run(handler("mykey myvalue"))
        self.assertIn("Warmed: 1", result)

    def test_cache_warm_no_args(self):
        handler = self.registered["cache-warm"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_cache_clear(self):
        # First warm, then clear
        warm_handler = self.registered["cache-warm"].handler
        asyncio.run(warm_handler("k1 v1"))
        handler = self.registered["cache-clear"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Cleared", result)

    def test_cache_clear_no_cache(self):
        # Fresh registry
        registry2 = MagicMock()
        registered2 = {}
        registry2.register = lambda cmd: registered2.__setitem__(cmd.name, cmd)
        from lidco.cli.commands import q195_cmds
        q195_cmds.register(registry2)
        handler = registered2["cache-clear"].handler
        result = asyncio.run(handler(""))
        self.assertIn("empty", result.lower())

    def test_token_optimize(self):
        handler = self.registered["token-optimize"].handler
        result = asyncio.run(handler("some   text   here"))
        self.assertIn("Original", result)
        self.assertIn("Compressed", result)

    def test_token_optimize_empty(self):
        handler = self.registered["token-optimize"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_all_commands_have_descriptions(self):
        for name, cmd in self.registered.items():
            self.assertIsInstance(cmd.description, str)
            self.assertTrue(len(cmd.description) > 0, f"{name} has empty description")

    def test_all_commands_have_handlers(self):
        for name, cmd in self.registered.items():
            self.assertTrue(callable(cmd.handler), f"{name} handler not callable")

    def test_cache_stats_after_warm(self):
        warm_handler = self.registered["cache-warm"].handler
        asyncio.run(warm_handler("k1 v1"))
        handler = self.registered["cache-stats"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Size: 1", result)

    def test_cache_warm_skip_existing(self):
        handler = self.registered["cache-warm"].handler
        asyncio.run(handler("same same_val"))
        result = asyncio.run(handler("same same_val"))
        self.assertIn("Skipped: 1", result)

    def test_token_optimize_with_newlines(self):
        handler = self.registered["token-optimize"].handler
        result = asyncio.run(handler("line1\n\n\n\nline2"))
        self.assertIn("Original", result)

    def test_cache_warm_key_with_spaces_in_value(self):
        handler = self.registered["cache-warm"].handler
        result = asyncio.run(handler("key value with spaces"))
        self.assertIn("Warmed: 1", result)


if __name__ == "__main__":
    unittest.main()
