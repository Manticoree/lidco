"""Tests for lidco.cli.commands.q302_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class _FakeRegistry:
    """Minimal registry for testing command registration."""

    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler) -> None:
        self.commands[name] = (desc, handler)


class TestQ302Commands(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q302_cmds import register_q302_commands

        self.registry = _FakeRegistry()
        register_q302_commands(self.registry)

    def test_all_commands_registered(self):
        self.assertIn("git-analyze", self.registry.commands)
        self.assertIn("smart-blame", self.registry.commands)
        self.assertIn("auto-bisect", self.registry.commands)
        self.assertIn("git-search", self.registry.commands)

    def test_git_analyze_no_args(self):
        _, handler = self.registry.commands["git-analyze"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_git_analyze_summary(self):
        _, handler = self.registry.commands["git-analyze"]
        result = asyncio.run(handler("summary"))
        self.assertIn("commit_count", result)

    def test_git_analyze_cadence(self):
        _, handler = self.registry.commands["git-analyze"]
        result = asyncio.run(handler("cadence"))
        self.assertIn("total_commits", result)

    def test_smart_blame_no_args(self):
        _, handler = self.registry.commands["smart-blame"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_smart_blame_with_file(self):
        _, handler = self.registry.commands["smart-blame"]
        result = asyncio.run(handler("main.py"))
        self.assertIn("main.py", result)

    def test_auto_bisect_no_args(self):
        _, handler = self.registry.commands["auto-bisect"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_auto_bisect_start_and_status(self):
        _, handler = self.registry.commands["auto-bisect"]
        result = asyncio.run(handler("start c0 c3 c0,c1,c2,c3"))
        self.assertIn("Bisect started", result)

    def test_auto_bisect_reset(self):
        _, handler = self.registry.commands["auto-bisect"]
        result = asyncio.run(handler("reset"))
        self.assertIn("cleared", result)

    def test_git_search_no_args(self):
        _, handler = self.registry.commands["git-search"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_git_search_messages(self):
        _, handler = self.registry.commands["git-search"]
        result = asyncio.run(handler("messages test"))
        # No commits loaded so expect no matches message
        self.assertIn("No matching", result)


if __name__ == "__main__":
    unittest.main()
