"""Tests for Q192 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q192_cmds import register, _state
from lidco.cli.commands.registry import CommandRegistry


def _run(coro):
    return asyncio.run(coro)


class TestQ192CmdsRegister(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.reg = CommandRegistry()
        register(self.reg)

    def test_commands_registered(self):
        for name in ("output-style", "explanatory", "learning", "brief"):
            cmd = self.reg._commands.get(name)
            self.assertIsNotNone(cmd, f"/{name} not registered")


class TestOutputStyleCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.reg = CommandRegistry()
        register(self.reg)
        self.handler = self.reg._commands["output-style"].handler

    def test_list_default(self):
        result = _run(self.handler(""))
        self.assertIn("Output styles", result)

    def test_set_default(self):
        result = _run(self.handler("set default"))
        self.assertIn("default", result)

    def test_set_unknown(self):
        result = _run(self.handler("set nonexistent"))
        self.assertIn("Unknown", result)

    def test_list_subcommand(self):
        result = _run(self.handler("list"))
        self.assertIn("Available styles", result)

    def test_usage(self):
        result = _run(self.handler("badcmd"))
        self.assertIn("Usage", result)


class TestExplanatoryCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.reg = CommandRegistry()
        register(self.reg)
        self.handler = self.reg._commands["explanatory"].handler

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Explanatory mode", result)

    def test_context(self):
        result = _run(self.handler("context Some important text"))
        self.assertIn("Rationale", result)

    def test_explain(self):
        result = _run(self.handler("explain Python"))
        self.assertIn("Python", result)

    def test_transform(self):
        result = _run(self.handler("transform Changed the config"))
        self.assertIn("Why:", result)

    def test_usage(self):
        result = _run(self.handler("badcmd"))
        self.assertIn("Usage", result)


class TestLearningCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.reg = CommandRegistry()
        register(self.reg)
        self.handler = self.reg._commands["learning"].handler

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Learning mode", result)

    def test_quiz(self):
        result = _run(self.handler("quiz loops"))
        self.assertIn("loops", result)

    def test_hint(self):
        result = _run(self.handler("hint recursion"))
        self.assertIn("recursion", result)

    def test_transform(self):
        result = _run(self.handler("transform Some text"))
        self.assertIn("Hint", result)

    def test_usage(self):
        result = _run(self.handler("badcmd"))
        self.assertIn("Usage", result)


class TestBriefCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.reg = CommandRegistry()
        register(self.reg)
        self.handler = self.reg._commands["brief"].handler

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Brief mode", result)

    def test_transform_text(self):
        result = _run(self.handler("transform hello world"))
        self.assertIn("hello", result)
