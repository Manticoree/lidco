"""Tests for Q209 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q209_cmds as q209_mod


def _make_registry():
    from lidco.cli.commands.registry import CommandRegistry

    cr = CommandRegistry.__new__(CommandRegistry)
    cr._commands = {}
    cr._session = None
    q209_mod._state.clear()
    q209_mod.register(cr)
    return cr


class TestQ209Commands(unittest.TestCase):
    def setUp(self):
        self.cr = _make_registry()

    def test_semantic_search_registered(self):
        self.assertIn("semantic-search", self.cr._commands)

    def test_intent_registered(self):
        self.assertIn("intent", self.cr._commands)

    def test_code_query_registered(self):
        self.assertIn("code-query", self.cr._commands)

    def test_context_assemble_registered(self):
        self.assertIn("context-assemble", self.cr._commands)

    def test_semantic_search_usage(self):
        handler = self.cr._commands["semantic-search"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_intent_usage(self):
        handler = self.cr._commands["intent"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_intent_classify(self):
        handler = self.cr._commands["intent"].handler
        result = asyncio.run(handler("find the auth function"))
        self.assertIn("Intent:", result)
        self.assertIn("find", result)

    def test_semantic_search_add_and_query(self):
        handler = self.cr._commands["semantic-search"].handler
        asyncio.run(handler("add test.py python authentication module"))
        result = asyncio.run(handler("query python authentication"))
        self.assertIn("result(s)", result)

    def test_code_query_usage(self):
        handler = self.cr._commands["code-query"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_context_assemble_usage(self):
        handler = self.cr._commands["context-assemble"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
