"""Tests for Q238 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q238_cmds as q238_mod


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.registry import CommandRegistry
        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q238_mod.register(reg)
        self._commands = reg._commands


class TestUltraplanCmd(_CmdTestBase):
    def test_create(self):
        handler = self._commands["ultraplan"].handler
        result = asyncio.run(handler("create My Plan: Build a feature"))
        self.assertIn("My Plan", result)
        self.assertIn("Overview", result)

    def test_critique(self):
        handler = self._commands["ultraplan"].handler
        result = asyncio.run(handler("critique My Plan"))
        self.assertIn("Critique", result)

    def test_summary(self):
        handler = self._commands["ultraplan"].handler
        result = asyncio.run(handler("summary My Plan"))
        self.assertIn("My Plan", result)

    def test_usage(self):
        handler = self._commands["ultraplan"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestUltrareviewCmd(_CmdTestBase):
    def test_review_code(self):
        handler = self._commands["ultrareview"].handler
        result = asyncio.run(handler("x = eval(input())"))
        self.assertIn("eval", result.lower())

    def test_empty_input(self):
        handler = self._commands["ultrareview"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestTurnLimitCmd(_CmdTestBase):
    def test_check(self):
        handler = self._commands["turn-limit"].handler
        result = asyncio.run(handler("check 50"))
        self.assertIn("continue", result)

    def test_usage(self):
        handler = self._commands["turn-limit"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestParallelToolsCmd(_CmdTestBase):
    def test_simulate(self):
        handler = self._commands["parallel-tools"].handler
        result = asyncio.run(handler("simulate read write grep"))
        self.assertIn("3 completed", result)

    def test_detect(self):
        handler = self._commands["parallel-tools"].handler
        result = asyncio.run(handler("detect read write read"))
        self.assertIn("batch", result.lower())

    def test_usage(self):
        handler = self._commands["parallel-tools"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
