"""Tests for lidco.cli.commands.q278_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q278_cmds import register_q278_commands


class _FakeRegistry:
    """Minimal registry that captures registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ278Commands(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q278_commands(self.registry)

    def test_commands_registered(self):
        names = set(self.registry.commands.keys())
        self.assertIn("profile-run", names)
        self.assertIn("flamegraph", names)
        self.assertIn("hotspots", names)
        self.assertIn("memory-profile", names)

    def test_profile_run_empty(self):
        handler = self.registry.commands["profile-run"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_profile_run_code(self):
        handler = self.registry.commands["profile-run"].handler
        result = asyncio.run(handler("x = 1"))
        self.assertIn("Profile", result)
        self.assertIn("Total time", result)

    def test_flamegraph_from_latest(self):
        handler = self.registry.commands["flamegraph"].handler
        result = asyncio.run(handler("from-latest x=1"))
        self.assertIn("ms", result)

    def test_flamegraph_export(self):
        handler = self.registry.commands["flamegraph"].handler
        result = asyncio.run(handler("export a=1"))
        self.assertIn("name", result)

    def test_hotspots_find(self):
        handler = self.registry.commands["hotspots"].handler
        result = asyncio.run(handler("find 5"))
        self.assertIn("hotspots", result.lower())

    def test_hotspots_suggest(self):
        handler = self.registry.commands["hotspots"].handler
        result = asyncio.run(handler("suggest"))
        self.assertIn("suggest", result.lower())

    def test_memory_profile_snapshot(self):
        handler = self.registry.commands["memory-profile"].handler
        result = asyncio.run(handler("snapshot test"))
        self.assertIn("Snapshot", result)


if __name__ == "__main__":
    unittest.main()
