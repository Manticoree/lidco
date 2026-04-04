"""Tests for lidco.cli.commands.q301_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q301_cmds import register_q301_commands


class _FakeRegistry:
    """Minimal registry that records registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ301Registration(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q301_commands(self.reg)

    def test_commands_registered(self):
        expected = {"conflict-detect", "conflict-resolve", "merge-strategy", "verify-merge"}
        self.assertEqual(set(self.reg.commands.keys()), expected)


class TestConflictDetectCmd(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q301_commands(self.reg)
        self.handler = self.reg.commands["conflict-detect"].handler

    def test_no_args_usage(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_with_overlap(self):
        result = asyncio.run(self.handler("a.py,b.py b.py,c.py"))
        self.assertIn("b.py", result)

    def test_no_overlap(self):
        result = asyncio.run(self.handler("a.py d.py"))
        self.assertIn("clean", result.lower())


class TestConflictResolveCmd(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q301_commands(self.reg)
        self.handler = self.reg.commands["conflict-resolve"].handler

    def test_help(self):
        result = asyncio.run(self.handler("help"))
        self.assertIn("Usage", result)

    def test_ours(self):
        result = asyncio.run(self.handler("ours"))
        self.assertIn("ours", result)

    def test_default_smart(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("smart", result)


class TestMergeStrategyCmd(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q301_commands(self.reg)
        self.handler = self.reg.commands["merge-strategy"].handler

    def test_recommend(self):
        result = asyncio.run(self.handler("recommend 1"))
        self.assertIn("squash", result)

    def test_compare(self):
        result = asyncio.run(self.handler("compare"))
        self.assertIn("merge", result)
        self.assertIn("rebase", result)

    def test_pros_cons(self):
        result = asyncio.run(self.handler("pros-cons rebase"))
        self.assertIn("rebase", result)


class TestVerifyMergeCmd(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q301_commands(self.reg)
        self.handler = self.reg.commands["verify-merge"].handler

    def test_check(self):
        result = asyncio.run(self.handler("check"))
        self.assertIn("PASS", result)

    def test_report(self):
        result = asyncio.run(self.handler("report"))
        self.assertIn("PASS", result)


if __name__ == "__main__":
    unittest.main()
