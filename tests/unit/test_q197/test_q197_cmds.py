"""Tests for Q197 CLI commands — task 1101."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q197_cmds import register


class _FakeRegistry:
    """Minimal registry mock that captures registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ197Registration(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register(self.registry)

    def test_suggest_registered(self):
        self.assertIn("suggest", self.registry.commands)

    def test_speculate_registered(self):
        self.assertIn("speculate", self.registry.commands)

    def test_prompt_history_registered(self):
        self.assertIn("prompt-history", self.registry.commands)

    def test_auto_complete_registered(self):
        self.assertIn("auto-complete", self.registry.commands)

    def test_all_four_commands(self):
        self.assertEqual(len(self.registry.commands), 4)


class TestSuggestHandler(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register(self.registry)
        self.handler = self.registry.commands["suggest"].handler

    def test_default_suggestions(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Suggestions:", result)

    def test_add_history(self):
        result = asyncio.run(self.handler("add fix the bug"))
        self.assertIn("Added to history", result)

    def test_with_count(self):
        result = asyncio.run(self.handler("3"))
        self.assertIn("Suggestions:", result)


class TestSpeculateHandler(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register(self.registry)
        self.handler = self.registry.commands["speculate"].handler

    def test_empty(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Not enough history", result)

    def test_with_prompt(self):
        result = asyncio.run(self.handler("list all files"))
        self.assertIn("Predicted:", result)
        self.assertIn("Confidence:", result)


class TestPromptHistoryHandler(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register(self.registry)
        self.handler = self.registry.commands["prompt-history"].handler

    def test_empty_history(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("No prompt history", result)


class TestAutoCompleteHandler(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register(self.registry)
        self.handler = self.registry.commands["auto-complete"].handler

    def test_no_prefix(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage:", result)

    def test_no_sources(self):
        result = asyncio.run(self.handler("test"))
        self.assertIn("No completions", result)


if __name__ == "__main__":
    unittest.main()
