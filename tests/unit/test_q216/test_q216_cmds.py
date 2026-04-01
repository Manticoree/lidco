"""Tests for cli.commands.q216_cmds — /profile-analyze, /bottlenecks, /optimize, /memory-check."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class TestQ216Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q216_cmds

        q216_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"profile-analyze", "bottlenecks", "optimize", "memory-check"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_profile_analyze_usage(self):
        handler = self.registered["profile-analyze"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_profile_analyze_with_args(self):
        handler = self.registered["profile-analyze"].handler
        result = asyncio.run(handler("my_func 100 2.5"))
        self.assertIn("my_func", result)
        self.assertIn("Profile:", result)

    def test_bottlenecks_usage(self):
        handler = self.registered["bottlenecks"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_bottlenecks_with_source(self):
        handler = self.registered["bottlenecks"].handler
        # Simple source that won't trigger bottlenecks
        result = asyncio.run(handler("x = 1"))
        self.assertIn("No bottlenecks", result)

    def test_optimize_usage(self):
        handler = self.registered["optimize"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_optimize_with_source(self):
        handler = self.registered["optimize"].handler
        result = asyncio.run(handler("x = 1"))
        self.assertIn("No optimizations", result)

    def test_memory_check_usage(self):
        handler = self.registered["memory-check"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_memory_check_with_source(self):
        handler = self.registered["memory-check"].handler
        result = asyncio.run(handler("x = 1"))
        self.assertIn("No memory issues", result)


if __name__ == "__main__":
    unittest.main()
