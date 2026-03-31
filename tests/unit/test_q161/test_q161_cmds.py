"""Tests for Q161 CLI commands (Task 921)."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q161_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ161Commands(unittest.TestCase):
    def setUp(self):
        q161_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q161_cmds.register(MockRegistry())

    def test_commands_registered(self):
        self.assertIn("continuation", self.registered)
        self.assertIn("tools-lazy", self.registered)
        self.assertIn("tool-search", self.registered)

    # --- /continuation ---

    def test_continuation_status_default(self):
        handler = self.registered["continuation"].handler
        result = _run(handler(""))
        self.assertIn("enabled", result)

    def test_continuation_on(self):
        handler = self.registered["continuation"].handler
        result = _run(handler("on"))
        self.assertIn("enabled", result.lower())

    def test_continuation_off(self):
        handler = self.registered["continuation"].handler
        result = _run(handler("off"))
        self.assertIn("disabled", result.lower())

    def test_continuation_status_after_off(self):
        handler = self.registered["continuation"].handler
        _run(handler("off"))
        result = _run(handler("status"))
        self.assertIn("disabled", result)

    def test_continuation_unknown_subcommand(self):
        handler = self.registered["continuation"].handler
        result = _run(handler("zzz"))
        self.assertIn("Usage", result)

    # --- /tools-lazy ---

    def test_tools_lazy_status_empty(self):
        handler = self.registered["tools-lazy"].handler
        result = _run(handler("status"))
        self.assertIn("Total tools: 0", result)

    def test_tools_lazy_resolve_missing(self):
        handler = self.registered["tools-lazy"].handler
        result = _run(handler("resolve nope"))
        self.assertIn("not found", result)

    def test_tools_lazy_resolve_no_name(self):
        handler = self.registered["tools-lazy"].handler
        result = _run(handler("resolve"))
        self.assertIn("Usage", result)

    def test_tools_lazy_search_no_query(self):
        handler = self.registered["tools-lazy"].handler
        result = _run(handler("search"))
        self.assertIn("Usage", result)

    def test_tools_lazy_search_no_match(self):
        handler = self.registered["tools-lazy"].handler
        result = _run(handler("search zzz"))
        self.assertIn("No tools", result)

    def test_tools_lazy_unknown_subcommand(self):
        handler = self.registered["tools-lazy"].handler
        result = _run(handler("zzz"))
        self.assertIn("Usage", result)

    # --- /tool-search ---

    def test_tool_search_no_query(self):
        handler = self.registered["tool-search"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_tool_search_no_match(self):
        handler = self.registered["tool-search"].handler
        result = _run(handler("xyz"))
        self.assertIn("No tools", result)


if __name__ == "__main__":
    unittest.main()
