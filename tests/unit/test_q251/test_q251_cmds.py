"""Tests for Q251 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q251_cmds import register
from lidco.cli.commands.registry import CommandRegistry, SlashCommand


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    def __init__(self):
        self.commands: dict[str, SlashCommand] = {}

    def register(self, cmd: SlashCommand):
        self.commands[cmd.name] = cmd


class TestRegistration(unittest.TestCase):
    def test_all_commands_registered(self):
        reg = _FakeRegistry()
        register(reg)
        self.assertIn("complete", reg.commands)
        self.assertIn("fill-middle", reg.commands)
        self.assertIn("snippet", reg.commands)
        self.assertIn("resolve-import", reg.commands)


class TestCompleteHandler(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register(self.reg)
        self.handler = self.reg.commands["complete"].handler

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_prefix_no_arg(self):
        result = _run(self.handler("prefix"))
        self.assertIn("Usage", result)

    def test_prefix_no_match(self):
        result = _run(self.handler("prefix xyz"))
        self.assertIn("No completions", result)

    def test_stats(self):
        result = _run(self.handler("stats"))
        self.assertIn("symbols=0", result)


class TestFillMiddleHandler(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register(self.reg)
        self.handler = self.reg.commands["fill-middle"].handler

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_fill_no_arg(self):
        result = _run(self.handler("fill"))
        self.assertIn("Usage", result)

    def test_fill_function(self):
        result = _run(self.handler("fill def foo():"))
        self.assertEqual(result, "pass")

    def test_suggest_no_arg(self):
        result = _run(self.handler("suggest"))
        self.assertIn("Usage", result)

    def test_indent(self):
        result = _run(self.handler("indent def foo():\n    return 1"))
        self.assertIn("Detected indent", result)


class TestSnippetHandler(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register(self.reg)
        self.handler = self.reg.commands["snippet"].handler

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_expand_missing(self):
        result = _run(self.handler("expand nope"))
        self.assertIn("No snippet", result)

    def test_list_empty(self):
        result = _run(self.handler("list"))
        self.assertIn("No snippets", result)

    def test_search_no_arg(self):
        result = _run(self.handler("search"))
        self.assertIn("Usage", result)


class TestResolveImportHandler(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register(self.reg)
        self.handler = self.reg.commands["resolve-import"].handler

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_resolve_no_arg(self):
        result = _run(self.handler("resolve"))
        self.assertIn("Usage", result)

    def test_resolve_no_match(self):
        result = _run(self.handler("resolve Foo"))
        self.assertIn("No modules", result)

    def test_suggest_no_arg(self):
        result = _run(self.handler("suggest"))
        self.assertIn("Usage", result)

    def test_missing_no_arg(self):
        result = _run(self.handler("missing"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
