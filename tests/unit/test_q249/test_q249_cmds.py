"""Tests for Q249 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q249_cmds as q249_mod


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.registry import CommandRegistry
        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q249_mod.register(reg)
        self._commands = reg._commands


class TestCodeGraphCmd(_CmdTestBase):
    def test_add(self):
        handler = self._commands["code-graph"].handler
        result = asyncio.run(handler("add myFunc function main.py"))
        self.assertIn("Added node myFunc", result)

    def test_add_missing_args(self):
        handler = self._commands["code-graph"].handler
        result = asyncio.run(handler("add foo"))
        self.assertIn("Usage", result)

    def test_show(self):
        handler = self._commands["code-graph"].handler
        result = asyncio.run(handler("show"))
        self.assertIn("nodes", result)
        self.assertIn("edges", result)

    def test_usage(self):
        handler = self._commands["code-graph"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestGraphQueryCmd(_CmdTestBase):
    def test_callers_empty(self):
        handler = self._commands["graph-query"].handler
        result = asyncio.run(handler("callers foo"))
        self.assertIn("No callers", result)

    def test_callers_missing_name(self):
        handler = self._commands["graph-query"].handler
        result = asyncio.run(handler("callers"))
        self.assertIn("Usage", result)

    def test_search_no_match(self):
        handler = self._commands["graph-query"].handler
        result = asyncio.run(handler("search zzz"))
        self.assertIn("No matches", result)

    def test_search_missing_pattern(self):
        handler = self._commands["graph-query"].handler
        result = asyncio.run(handler("search"))
        self.assertIn("Usage", result)

    def test_usage(self):
        handler = self._commands["graph-query"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestImpactCmd(_CmdTestBase):
    def test_analyze(self):
        handler = self._commands["impact"].handler
        result = asyncio.run(handler("analyze foo"))
        self.assertIn("Affected", result)
        self.assertIn("confidence", result)

    def test_analyze_missing(self):
        handler = self._commands["impact"].handler
        result = asyncio.run(handler("analyze"))
        self.assertIn("Usage", result)

    def test_files_empty(self):
        handler = self._commands["impact"].handler
        result = asyncio.run(handler("files foo"))
        self.assertIn("No affected files", result)

    def test_files_missing(self):
        handler = self._commands["impact"].handler
        result = asyncio.run(handler("files"))
        self.assertIn("Usage", result)

    def test_usage(self):
        handler = self._commands["impact"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestGraphVizCmd(_CmdTestBase):
    def test_dot(self):
        handler = self._commands["graph-viz"].handler
        result = asyncio.run(handler("dot"))
        self.assertIn("digraph", result)

    def test_mermaid(self):
        handler = self._commands["graph-viz"].handler
        result = asyncio.run(handler("mermaid"))
        self.assertIn("flowchart", result)

    def test_filter(self):
        handler = self._commands["graph-viz"].handler
        result = asyncio.run(handler("filter main.py"))
        self.assertIn("digraph", result)

    def test_filter_missing(self):
        handler = self._commands["graph-viz"].handler
        result = asyncio.run(handler("filter"))
        self.assertIn("Usage", result)

    def test_usage(self):
        handler = self._commands["graph-viz"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
