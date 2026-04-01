"""Tests for cli.commands.q235_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.registry import CommandRegistry, SlashCommand
from lidco.cli.commands.q235_cmds import register


class TestQ235Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CommandRegistry()
        register(self.registry)

    def test_thinkback_registered(self) -> None:
        cmd = self.registry.get("thinkback")
        self.assertIsNotNone(cmd)
        self.assertIsInstance(cmd, SlashCommand)

    def test_thinking_search_registered(self) -> None:
        cmd = self.registry.get("thinking-search")
        self.assertIsNotNone(cmd)

    def test_thinking_stats_registered(self) -> None:
        cmd = self.registry.get("thinking-stats")
        self.assertIsNotNone(cmd)

    def test_thinking_diff_registered(self) -> None:
        cmd = self.registry.get("thinking-diff")
        self.assertIsNotNone(cmd)

    def test_thinkback_with_turn_and_content(self) -> None:
        cmd = self.registry.get("thinkback")
        result = asyncio.run(cmd.handler("1 I think this is correct"))
        self.assertIn("Turn 1", result)

    def test_thinkback_invalid_turn(self) -> None:
        cmd = self.registry.get("thinkback")
        result = asyncio.run(cmd.handler("abc"))
        self.assertIn("Invalid turn", result)

    def test_thinking_search_no_args(self) -> None:
        cmd = self.registry.get("thinking-search")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_thinking_search_with_query(self) -> None:
        cmd = self.registry.get("thinking-search")
        result = asyncio.run(cmd.handler("decision"))
        self.assertIn("decision", result)

    def test_thinking_stats_handler(self) -> None:
        cmd = self.registry.get("thinking-stats")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("ThinkingStore", result)
        self.assertIn("ThinkingAnalyzer", result)

    def test_thinking_diff_no_pipe(self) -> None:
        cmd = self.registry.get("thinking-diff")
        result = asyncio.run(cmd.handler("single block"))
        self.assertIn("Usage", result)

    def test_thinking_diff_with_pipe(self) -> None:
        cmd = self.registry.get("thinking-diff")
        result = asyncio.run(cmd.handler("old line | new line"))
        self.assertIn("- old line", result)
        self.assertIn("+ new line", result)


if __name__ == "__main__":
    unittest.main()
