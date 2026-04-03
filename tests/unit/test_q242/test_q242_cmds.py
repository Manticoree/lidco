"""Tests for Q242 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


class TestQ242Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}
        def _register(cmd):
            self.registered[cmd.name] = cmd
        self.registry.register = _register
        from lidco.cli.commands.q242_cmds import register
        register(self.registry)

    def test_all_commands_registered(self):
        expected = {"branch-tree", "branch-nav", "branch-compare", "branch-prune"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_branch_tree_no_args(self):
        result = _run(self.registered["branch-tree"].handler(""))
        self.assertIn("Usage", result)

    def test_branch_tree_list(self):
        result = _run(self.registered["branch-tree"].handler("list"))
        self.assertIsInstance(result, str)

    def test_branch_nav_no_args(self):
        result = _run(self.registered["branch-nav"].handler(""))
        self.assertIn("Usage", result)

    def test_branch_compare_no_args(self):
        result = _run(self.registered["branch-compare"].handler(""))
        self.assertIn("Usage", result)

    def test_branch_prune_no_args(self):
        result = _run(self.registered["branch-prune"].handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
