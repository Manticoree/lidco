"""Tests for Q165 CLI commands (Task 941)."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q165_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ165Registration(unittest.TestCase):
    def setUp(self):
        q165_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q165_cmds.register(MockRegistry())

    def test_fork_registered(self):
        self.assertIn("fork", self.registered)

    def test_branch_registered(self):
        self.assertIn("branch", self.registered)

    def test_branch_diff_registered(self):
        self.assertIn("branch-diff", self.registered)

    def test_loop_registered(self):
        self.assertIn("loop", self.registered)


class TestForkCommand(unittest.TestCase):
    def setUp(self):
        q165_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q165_cmds.register(MockRegistry())

    def test_fork_default_label(self):
        result = _run(self.registered["fork"].handler(""))
        self.assertIn("Forked to branch", result)
        self.assertIn("fork", result)

    def test_fork_custom_label(self):
        result = _run(self.registered["fork"].handler("experiment"))
        self.assertIn("experiment", result)


class TestBranchCommand(unittest.TestCase):
    def setUp(self):
        q165_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q165_cmds.register(MockRegistry())
        self.handler = self.registered["branch"].handler

    def test_list_empty(self):
        result = _run(self.handler("list"))
        self.assertIn("No branches", result)

    def test_list_after_fork(self):
        _run(self.registered["fork"].handler("test"))
        result = _run(self.handler("list"))
        self.assertIn("test", result)

    def test_switch_missing(self):
        result = _run(self.handler("switch nonexistent"))
        self.assertIn("not found", result)

    def test_delete_missing(self):
        result = _run(self.handler("delete nonexistent"))
        self.assertIn("not found", result)

    def test_switch_no_id(self):
        result = _run(self.handler("switch"))
        self.assertIn("Usage", result)

    def test_delete_no_id(self):
        result = _run(self.handler("delete"))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    def test_no_args_shows_list(self):
        result = _run(self.handler(""))
        self.assertIn("No branches", result)


class TestBranchDiffCommand(unittest.TestCase):
    def setUp(self):
        q165_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q165_cmds.register(MockRegistry())

    def test_missing_args(self):
        result = _run(self.registered["branch-diff"].handler(""))
        self.assertIn("Usage", result)

    def test_missing_branch(self):
        result = _run(self.registered["branch-diff"].handler("aaa bbb"))
        self.assertIn("not found", result)


class TestLoopCommand(unittest.TestCase):
    def setUp(self):
        q165_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q165_cmds.register(MockRegistry())
        self.handler = self.registered["loop"].handler

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_execute_once(self):
        result = _run(self.handler("1s /status"))
        self.assertIn("/status", result)

    def test_invalid_interval(self):
        result = _run(self.handler("abc /status"))
        self.assertIn("Invalid interval", result)


if __name__ == "__main__":
    unittest.main()
