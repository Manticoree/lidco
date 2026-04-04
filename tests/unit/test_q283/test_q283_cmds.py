"""Tests for lidco.cli.commands.q283_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q283_cmds import register, _state


class _FakeRegistry:
    """Minimal registry that captures registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ283Commands(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.registry = _FakeRegistry()
        register(self.registry)

    def test_all_commands_registered(self):
        names = set(self.registry.commands.keys())
        self.assertIn("adapt-prompt", names)
        self.assertIn("rank-context", names)
        self.assertIn("select-examples", names)
        self.assertIn("style-match", names)

    # -- /adapt-prompt --

    def test_adapt_prompt_no_args(self):
        handler = self.registry.commands["adapt-prompt"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Supported types", result)

    def test_adapt_prompt_show_template(self):
        handler = self.registry.commands["adapt-prompt"].handler
        result = asyncio.run(handler("code"))
        self.assertIn("Template", result)

    def test_adapt_prompt_adapt(self):
        handler = self.registry.commands["adapt-prompt"].handler
        result = asyncio.run(handler("code write a sort function"))
        self.assertIn("sort function", result)

    def test_adapt_prompt_unknown_type(self):
        handler = self.registry.commands["adapt-prompt"].handler
        result = asyncio.run(handler("bogus_type do something"))
        self.assertIn("Unknown task type", result)

    # -- /rank-context --

    def test_rank_context_no_args(self):
        handler = self.registry.commands["rank-context"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Context items", result)

    def test_rank_context_add_and_rank(self):
        handler = self.registry.commands["rank-context"].handler
        asyncio.run(handler("add python sorting algorithms"))
        asyncio.run(handler("add cooking recipes"))
        result = asyncio.run(handler("rank python"))
        self.assertIn("Ranked", result)

    def test_rank_context_clear(self):
        handler = self.registry.commands["rank-context"].handler
        asyncio.run(handler("add something"))
        result = asyncio.run(handler("clear"))
        self.assertIn("cleared", result.lower())

    def test_rank_context_rank_empty(self):
        handler = self.registry.commands["rank-context"].handler
        _state.pop("ranker", None)
        result = asyncio.run(handler("rank query"))
        self.assertIn("No context items", result)

    # -- /select-examples --

    def test_select_examples_no_args(self):
        handler = self.registry.commands["select-examples"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Examples", result)

    def test_select_examples_add_and_select(self):
        handler = self.registry.commands["select-examples"].handler
        asyncio.run(handler("add code | sort a list | sorted_list = sorted(data)"))
        result = asyncio.run(handler("select code"))
        self.assertIn("Selected", result)

    def test_select_examples_clear(self):
        handler = self.registry.commands["select-examples"].handler
        asyncio.run(handler("add code | x | y"))
        result = asyncio.run(handler("clear"))
        self.assertIn("cleared", result.lower())

    # -- /style-match --

    def test_style_match_no_args(self):
        handler = self.registry.commands["style-match"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_style_match_analyze(self):
        handler = self.registry.commands["style-match"].handler
        result = asyncio.run(handler("analyze my_var = get_value()"))
        self.assertIn("naming", result)

    def test_style_match_naming(self):
        handler = self.registry.commands["style-match"].handler
        result = asyncio.run(handler("naming myVariable = getValue()"))
        self.assertIn("camelCase", result)

    def test_style_match_match(self):
        handler = self.registry.commands["style-match"].handler
        result = asyncio.run(handler("match my_func = get_data()"))
        self.assertIn("Matched style", result)


if __name__ == "__main__":
    unittest.main()
