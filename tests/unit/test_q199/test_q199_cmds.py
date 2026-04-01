"""Tests for Q199 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.query.executor import QueryExecutor, SymbolRecord

import lidco.cli.commands.q199_cmds as q199_mod


def _setup_state():
    """Inject test executor into module state."""
    q199_mod._state.clear()
    executor = QueryExecutor([
        SymbolRecord(name="foo", kind="function", file="a.py", line=10),
        SymbolRecord(name="Bar", kind="class", file="b.py", line=20),
        SymbolRecord(name="baz", kind="function", file="a.py", line=30),
    ])
    q199_mod._state["executor"] = executor
    return executor


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        self.executor = _setup_state()
        from lidco.cli.commands.registry import CommandRegistry
        cr = CommandRegistry.__new__(CommandRegistry)
        cr._commands = {}
        cr._session = None
        q199_mod.register(cr)
        self.query = cr._commands["query"].handler
        self.ast_query = cr._commands["ast-query"].handler
        self.query_cache = cr._commands["query-cache"].handler
        self.query_explain = cr._commands["query-explain"].handler


class TestQueryCommand(_CmdTestBase):
    def test_query_select(self):
        result = asyncio.run(self.query("SELECT name, kind"))
        self.assertIn("3 result(s)", result)
        self.assertIn("foo", result)

    def test_query_where(self):
        result = asyncio.run(self.query("SELECT name WHERE kind = 'function'"))
        self.assertIn("2 result(s)", result)
        self.assertNotIn("Bar", result)

    def test_query_empty(self):
        result = asyncio.run(self.query(""))
        self.assertIn("Usage", result)

    def test_query_parse_error(self):
        result = asyncio.run(self.query("INVALID"))
        self.assertIn("Parse error", result)


class TestQueryExplainCommand(_CmdTestBase):
    def test_explain(self):
        result = asyncio.run(self.query_explain("SELECT name WHERE kind = 'function' ORDER BY name LIMIT 5"))
        self.assertIn("Query plan", result)
        self.assertIn("SELECT", result)
        self.assertIn("WHERE", result)
        self.assertIn("ORDER BY", result)
        self.assertIn("LIMIT", result)

    def test_explain_empty(self):
        result = asyncio.run(self.query_explain(""))
        self.assertIn("Usage", result)


class TestAstQueryCommand(_CmdTestBase):
    def test_no_ast_loaded(self):
        result = asyncio.run(self.ast_query("function"))
        self.assertIn("No AST loaded", result)

    def test_empty(self):
        result = asyncio.run(self.ast_query(""))
        self.assertIn("Usage", result)


class TestQueryCacheCommand(_CmdTestBase):
    def test_stats(self):
        result = asyncio.run(self.query_cache("stats"))
        self.assertIn("Cache stats", result)

    def test_clear(self):
        result = asyncio.run(self.query_cache("clear"))
        self.assertIn("cleared", result)

    def test_help(self):
        result = asyncio.run(self.query_cache(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
