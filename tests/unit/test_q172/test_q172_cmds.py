"""Tests for lidco.cli.commands.q172_cmds."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from lidco.cli.commands.q172_cmds import register_q172_commands, _state


class _FakeRegistry:
    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def register(self, cmd: object) -> None:
        self.commands[cmd.name] = cmd  # type: ignore[attr-defined]


class TestRegisterCommands(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()

    def test_register_q172_commands(self) -> None:
        reg = _FakeRegistry()
        register_q172_commands(reg)
        self.assertIn("index", reg.commands)
        self.assertIn("search", reg.commands)
        self.assertIn("context-sources", reg.commands)
        self.assertEqual(len(reg.commands), 3)


class TestIndexHandler(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()

    def _get_handler(self):
        reg = _FakeRegistry()
        register_q172_commands(reg)
        return reg.commands["index"].handler

    def test_index_build(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("build"))
        self.assertIn("Indexing started", result)

    def test_index_status(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("status"))
        self.assertIn("Index status:", result)
        self.assertIn("0 entries", result)

    def test_index_clear(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("clear"))
        self.assertIn("Index cleared:", result)

    def test_index_no_args(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("Usage:", result)


class TestSearchHandler(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()

    def _get_handler(self):
        reg = _FakeRegistry()
        register_q172_commands(reg)
        return reg.commands["search"].handler

    def test_search_no_query(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("Usage:", result)

    def test_search_no_results(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("nonexistent_query_xyz"))
        self.assertIn("No results found for:", result)

    def test_search_hybrid(self) -> None:
        handler = self._get_handler()
        # Empty store returns no results
        result = asyncio.run(handler("hello world"))
        self.assertIn("No results found", result)

    def test_search_semantic_flag(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("hello --semantic"))
        # Should parse the flag and still return no results from empty store
        self.assertIn("No results found", result)

    def test_search_keyword_flag(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("hello --keyword"))
        self.assertIn("No results found", result)


class TestContextSourcesHandler(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()

    def _get_handler(self):
        reg = _FakeRegistry()
        register_q172_commands(reg)
        return reg.commands["context-sources"].handler

    def test_context_sources(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("Auto-context injection: enabled", result)
        self.assertIn("Max snippets: 5", result)
        self.assertIn("Max tokens: 2000", result)


if __name__ == "__main__":
    unittest.main()
