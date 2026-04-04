"""Tests for lidco.cli.commands.q303_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q303_cmds import register_q303_commands


class _FakeRegistry:
    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestRegisterQ303Commands(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q303_commands(self.reg)

    def test_all_commands_registered(self):
        expected = {"branch-strategy", "branch-cleanup", "branch-dashboard", "worktree"}
        self.assertEqual(set(self.reg.commands.keys()), expected)

    # /branch-strategy
    def test_branch_strategy_rules(self):
        handler = self.reg.commands["branch-strategy"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Strategy", result)

    def test_branch_strategy_set(self):
        handler = self.reg.commands["branch-strategy"].handler
        result = asyncio.run(handler("set gitflow"))
        self.assertIn("gitflow", result)

    def test_branch_strategy_validate(self):
        handler = self.reg.commands["branch-strategy"].handler
        result = asyncio.run(handler("validate feature/test"))
        self.assertIn("valid", result)

    def test_branch_strategy_create(self):
        handler = self.reg.commands["branch-strategy"].handler
        result = asyncio.run(handler("create feature my-thing"))
        self.assertIn("feature/my-thing", result)

    def test_branch_strategy_prefixes(self):
        handler = self.reg.commands["branch-strategy"].handler
        result = asyncio.run(handler("prefixes"))
        self.assertIn("feature/", result)

    # /branch-cleanup
    def test_branch_cleanup_stale(self):
        handler = self.reg.commands["branch-cleanup"].handler
        result = asyncio.run(handler("stale"))
        self.assertIn("No stale", result)

    def test_branch_cleanup_merged(self):
        handler = self.reg.commands["branch-cleanup"].handler
        result = asyncio.run(handler("merged"))
        self.assertIn("No merged", result)

    def test_branch_cleanup_orphaned(self):
        handler = self.reg.commands["branch-cleanup"].handler
        result = asyncio.run(handler("orphaned"))
        self.assertIn("No orphaned", result)

    # /branch-dashboard
    def test_branch_dashboard_summary(self):
        handler = self.reg.commands["branch-dashboard"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Total branches", result)

    def test_branch_dashboard_overview(self):
        handler = self.reg.commands["branch-dashboard"].handler
        result = asyncio.run(handler("overview"))
        self.assertIn("No branches", result)

    def test_branch_dashboard_authors(self):
        handler = self.reg.commands["branch-dashboard"].handler
        result = asyncio.run(handler("authors"))
        self.assertIn("No authors", result)

    # /worktree
    def test_worktree_list(self):
        handler = self.reg.commands["worktree"].handler
        result = asyncio.run(handler(""))
        self.assertIn("No worktrees", result)

    def test_worktree_create(self):
        handler = self.reg.commands["worktree"].handler
        result = asyncio.run(handler("create feature/x /tmp/wt"))
        self.assertIn("Created", result)

    def test_worktree_cache(self):
        handler = self.reg.commands["worktree"].handler
        result = asyncio.run(handler("cache"))
        self.assertIn("cache", result)


if __name__ == "__main__":
    unittest.main()
