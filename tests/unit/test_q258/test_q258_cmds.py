"""Tests for Q258 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q258_cmds as q258_mod


def _run(coro):
    return asyncio.run(coro)


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        q258_mod._state.clear()
        from lidco.cli.commands.registry import CommandRegistry
        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q258_mod.register(reg)
        self.doc_coverage = reg._commands["doc-coverage"].handler
        self.gen_docs = reg._commands["gen-docs"].handler
        self.lint_docs = reg._commands["lint-docs"].handler
        self.search_docs = reg._commands["search-docs"].handler


class TestDocCoverageCmd(_CmdTestBase):
    def test_empty_args(self):
        result = _run(self.doc_coverage(""))
        self.assertIn("Usage", result)

    def test_analyze(self):
        src = 'def foo():\n    """Doc."""\n    pass\n'
        result = _run(self.doc_coverage(src))
        self.assertIn("100.0%", result)

    def test_undocumented(self):
        src = "def foo():\n    pass\n"
        result = _run(self.doc_coverage(src))
        self.assertIn("foo", result)

    def test_syntax_error(self):
        result = _run(self.doc_coverage("def (broken"))
        self.assertIn("Error", result)


class TestGenDocsCmd(_CmdTestBase):
    def test_empty_args(self):
        result = _run(self.gen_docs(""))
        self.assertIn("Usage", result)

    def test_module(self):
        src = 'def foo():\n    """Doc."""\n    pass\n'
        result = _run(self.gen_docs(f"module mymod {src}"))
        self.assertIn("mymod", result)

    def test_function(self):
        src = 'def add(a: int, b: int) -> int:\n    """Add."""\n    return a + b\n'
        result = _run(self.gen_docs(f"function add {src}"))
        self.assertIn("add", result)

    def test_class(self):
        src = 'class Dog:\n    """A dog."""\n    pass\n'
        result = _run(self.gen_docs(f"class Dog {src}"))
        self.assertIn("Dog", result)

    def test_function_no_source(self):
        result = _run(self.gen_docs("function"))
        self.assertIn("Usage", result)

    def test_module_no_source(self):
        result = _run(self.gen_docs("module mymod"))
        self.assertIn("Usage", result)

    def test_unknown_sub(self):
        result = _run(self.gen_docs("xyz"))
        self.assertIn("Usage", result)


class TestLintDocsCmd(_CmdTestBase):
    def test_empty_args(self):
        result = _run(self.lint_docs(""))
        self.assertIn("Usage", result)

    def test_clean(self):
        src = 'def foo():\n    """Do foo."""\n    pass\n'
        result = _run(self.lint_docs(src))
        self.assertIn("No documentation lint issues", result)

    def test_issues_found(self):
        src = "def foo():\n    pass\n"
        result = _run(self.lint_docs(src))
        self.assertIn("issue(s)", result)
        self.assertIn("missing-docstring", result)

    def test_syntax_error(self):
        result = _run(self.lint_docs("def (broken"))
        self.assertIn("Error", result)


class TestSearchDocsCmd(_CmdTestBase):
    def test_empty_args(self):
        result = _run(self.search_docs(""))
        self.assertIn("Usage", result)

    def test_index_and_query(self):
        _run(self.search_docs("index Python Guide | Python programming language"))
        result = _run(self.search_docs("query python"))
        self.assertIn("Python Guide", result)

    def test_index_no_pipe(self):
        result = _run(self.search_docs("index title without pipe"))
        self.assertIn("Usage", result)

    def test_query_no_results(self):
        result = _run(self.search_docs("query nonexistent_xyz"))
        self.assertIn("No results", result)

    def test_clear(self):
        _run(self.search_docs("index A | Alpha"))
        result = _run(self.search_docs("clear"))
        self.assertIn("cleared", result)

    def test_stats_empty(self):
        result = _run(self.search_docs("stats"))
        self.assertIn("0 docs", result)

    def test_stats_after_index(self):
        _run(self.search_docs("index Hello | World content"))
        result = _run(self.search_docs("stats"))
        self.assertIn("1 docs", result)

    def test_unknown_sub(self):
        result = _run(self.search_docs("xyz"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
