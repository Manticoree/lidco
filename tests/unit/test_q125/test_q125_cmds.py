"""Tests for Q125 CLI commands (/symbols)."""
from __future__ import annotations
import asyncio
import unittest
from lidco.cli.commands import q125_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ125Commands(unittest.TestCase):
    def setUp(self):
        q125_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q125_cmds.register(MockRegistry())
        self.handler = self.registered["symbols"].handler

    def test_command_registered(self):
        self.assertIn("symbols", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_sub_shows_usage(self):
        result = _run(self.handler("bogus"))
        self.assertIn("Usage", result)

    def test_extract_basic(self):
        result = _run(self.handler("extract def foo(): pass"))
        self.assertIn("Extracted", result)

    def test_extract_no_args(self):
        result = _run(self.handler("extract"))
        self.assertIn("Usage", result)

    def test_extract_syntax_error(self):
        result = _run(self.handler("extract def foo("))
        self.assertIn("error", result.lower())

    def test_find_after_extract(self):
        _run(self.handler("extract def bar(): pass"))
        result = _run(self.handler("find bar"))
        self.assertIn("bar", result)
        self.assertIn("function", result)

    def test_find_missing(self):
        result = _run(self.handler("find nonexistent"))
        self.assertIn("not found", result)

    def test_find_no_args(self):
        result = _run(self.handler("find"))
        self.assertIn("Usage", result)

    def test_list_empty(self):
        result = _run(self.handler("list"))
        self.assertIn("No symbols", result)

    def test_list_after_extract(self):
        _run(self.handler("extract def alpha(): pass"))
        result = _run(self.handler("list"))
        self.assertIn("alpha", result)

    def test_list_by_kind(self):
        _run(self.handler("extract class MyClass: pass"))
        result = _run(self.handler("list class"))
        self.assertIn("MyClass", result)

    def test_list_wrong_kind_empty(self):
        _run(self.handler("extract def foo(): pass"))
        result = _run(self.handler("list class"))
        self.assertIn("No symbols", result)

    def test_xref_no_args(self):
        result = _run(self.handler("xref"))
        self.assertIn("Usage", result)

    def test_xref_after_extract(self):
        _run(self.handler("extract def myfunc(): pass"))
        result = _run(self.handler("xref myfunc"))
        # Should show definition info (module/line)
        self.assertIn("<input>", result)

    def test_xref_undefined(self):
        result = _run(self.handler("xref ghost"))
        self.assertIn("Not defined", result)

    def test_unused_empty(self):
        result = _run(self.handler("unused"))
        self.assertIn("No unused", result)

    def test_unused_shows_symbols(self):
        _run(self.handler("extract def unreferenced(): pass"))
        result = _run(self.handler("unused"))
        # unreferenced has no refs, so it appears
        self.assertIn("unreferenced", result)

    def test_clear(self):
        _run(self.handler("extract def foo(): pass"))
        result = _run(self.handler("clear"))
        self.assertIn("cleared", result.lower())

    def test_clear_then_list_empty(self):
        _run(self.handler("extract def foo(): pass"))
        _run(self.handler("clear"))
        result = _run(self.handler("list"))
        self.assertIn("No symbols", result)

    def test_description_set(self):
        self.assertIn("symbol", self.registered["symbols"].description.lower())

    def test_extract_class(self):
        result = _run(self.handler("extract class MyClass: pass"))
        self.assertIn("Extracted", result)

    def test_extract_multiple(self):
        _run(self.handler("extract def a(): pass"))
        _run(self.handler("extract def b(): pass"))
        result = _run(self.handler("list"))
        self.assertIn("a", result)
        self.assertIn("b", result)


if __name__ == "__main__":
    unittest.main()
