"""Tests for lidco.cli.commands.q222_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.registry import CommandRegistry, SlashCommand
from lidco.cli.commands.q222_cmds import register


def _run(coro):
    return asyncio.run(coro)


class TestQ222Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CommandRegistry()
        register(self.registry)

    def test_all_commands_registered(self) -> None:
        names = {"tool-cache", "cache-stats", "cache-invalidate", "dedup-stats"}
        for name in names:
            self.assertIn(name, self.registry._commands, f"/{name} not registered")

    def test_tool_cache_no_args(self) -> None:
        handler = self.registry._commands["tool-cache"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_tool_cache_put(self) -> None:
        handler = self.registry._commands["tool-cache"].handler
        result = _run(handler("grep pattern found_it"))
        self.assertIn("Cached", result)

    def test_tool_cache_get_miss(self) -> None:
        handler = self.registry._commands["tool-cache"].handler
        result = _run(handler("grep nope"))
        self.assertIn("No cached", result)

    def test_cache_stats(self) -> None:
        handler = self.registry._commands["cache-stats"].handler
        result = _run(handler(""))
        self.assertIn("ToolResultCache", result)

    def test_cache_invalidate_no_args(self) -> None:
        handler = self.registry._commands["cache-invalidate"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_cache_invalidate_with_path(self) -> None:
        handler = self.registry._commands["cache-invalidate"].handler
        result = _run(handler("/src/a.py"))
        self.assertIn("Invalidated", result)

    def test_dedup_stats(self) -> None:
        handler = self.registry._commands["dedup-stats"].handler
        result = _run(handler(""))
        self.assertIn("DedupEngine", result)


if __name__ == "__main__":
    unittest.main()
