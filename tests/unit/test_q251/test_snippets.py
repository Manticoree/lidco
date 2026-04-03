"""Tests for SnippetExpander (Q251)."""
from __future__ import annotations

import unittest

from lidco.completion.snippets import Snippet, SnippetExpander


def _snip(**overrides) -> Snippet:
    defaults = dict(name="test", trigger="tst", body="test body")
    defaults.update(overrides)
    return Snippet(**defaults)


class TestSnippetDataclass(unittest.TestCase):
    def test_basic_fields(self):
        s = Snippet(name="fn", trigger="fn", body="def ${name}():\n    pass")
        self.assertEqual(s.name, "fn")
        self.assertEqual(s.trigger, "fn")
        self.assertIn("${name}", s.body)

    def test_default_description(self):
        s = _snip()
        self.assertEqual(s.description, "")

    def test_default_tags(self):
        s = _snip()
        self.assertEqual(s.tags, ())

    def test_frozen(self):
        s = _snip()
        with self.assertRaises(AttributeError):
            s.name = "x"  # type: ignore[misc]

    def test_tags_as_tuple(self):
        s = Snippet(name="a", trigger="a", body="b", tags=("python", "util"))
        self.assertEqual(s.tags, ("python", "util"))


class TestAdd(unittest.TestCase):
    def test_add_one(self):
        exp = SnippetExpander()
        exp.add(_snip())
        self.assertEqual(len(exp.list_all()), 1)

    def test_add_multiple(self):
        exp = SnippetExpander()
        exp.add(_snip(name="a", trigger="a"))
        exp.add(_snip(name="b", trigger="b"))
        self.assertEqual(len(exp.list_all()), 2)

    def test_add_overwrite(self):
        exp = SnippetExpander()
        exp.add(_snip(name="a", trigger="a", body="old"))
        exp.add(_snip(name="a", trigger="a", body="new"))
        self.assertEqual(len(exp.list_all()), 1)
        self.assertEqual(exp.expand("a"), "new")


class TestRemove(unittest.TestCase):
    def test_remove_existing(self):
        exp = SnippetExpander()
        exp.add(_snip(name="a"))
        self.assertTrue(exp.remove("a"))
        self.assertEqual(len(exp.list_all()), 0)

    def test_remove_nonexistent(self):
        exp = SnippetExpander()
        self.assertFalse(exp.remove("nope"))


class TestExpand(unittest.TestCase):
    def test_simple_expand(self):
        exp = SnippetExpander()
        exp.add(_snip(trigger="fn", body="def ${name}():\n    pass"))
        result = exp.expand("fn", {"name": "hello"})
        self.assertEqual(result, "def hello():\n    pass")

    def test_expand_no_vars(self):
        exp = SnippetExpander()
        exp.add(_snip(trigger="main", body="if __name__ == '__main__':\n    main()"))
        result = exp.expand("main")
        self.assertIn("__main__", result)

    def test_expand_missing_trigger(self):
        exp = SnippetExpander()
        self.assertIsNone(exp.expand("nope"))

    def test_expand_multiple_vars(self):
        exp = SnippetExpander()
        exp.add(_snip(trigger="cls", body="class ${name}(${base}):\n    pass"))
        result = exp.expand("cls", {"name": "Foo", "base": "Bar"})
        self.assertEqual(result, "class Foo(Bar):\n    pass")

    def test_expand_unused_var_placeholder_remains(self):
        exp = SnippetExpander()
        exp.add(_snip(trigger="x", body="${a} ${b}"))
        result = exp.expand("x", {"a": "1"})
        self.assertEqual(result, "1 ${b}")


class TestSearch(unittest.TestCase):
    def test_search_by_name(self):
        exp = SnippetExpander()
        exp.add(_snip(name="function", trigger="fn"))
        found = exp.search("func")
        self.assertEqual(len(found), 1)

    def test_search_by_trigger(self):
        exp = SnippetExpander()
        exp.add(_snip(name="x", trigger="fnc"))
        found = exp.search("fnc")
        self.assertEqual(len(found), 1)

    def test_search_by_description(self):
        exp = SnippetExpander()
        exp.add(_snip(name="x", trigger="y", description="Creates a Python function"))
        found = exp.search("python")
        self.assertEqual(len(found), 1)

    def test_search_by_tag(self):
        exp = SnippetExpander()
        exp.add(Snippet(name="x", trigger="y", body="z", tags=("python", "util")))
        found = exp.search("util")
        self.assertEqual(len(found), 1)

    def test_search_no_match(self):
        exp = SnippetExpander()
        exp.add(_snip())
        found = exp.search("zzzz")
        self.assertEqual(len(found), 0)

    def test_search_case_insensitive(self):
        exp = SnippetExpander()
        exp.add(_snip(name="FunctionDef"))
        found = exp.search("functiondef")
        self.assertEqual(len(found), 1)


class TestListAll(unittest.TestCase):
    def test_empty(self):
        exp = SnippetExpander()
        self.assertEqual(exp.list_all(), [])

    def test_returns_all(self):
        exp = SnippetExpander()
        exp.add(_snip(name="a", trigger="a"))
        exp.add(_snip(name="b", trigger="b"))
        self.assertEqual(len(exp.list_all()), 2)


if __name__ == "__main__":
    unittest.main()
