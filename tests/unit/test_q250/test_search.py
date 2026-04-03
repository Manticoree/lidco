"""Tests for PolyglotSearch (Q250)."""
from __future__ import annotations

import unittest

from lidco.polyglot.parser import Symbol
from lidco.polyglot.search import PolyglotSearch


class TestNormalizeName(unittest.TestCase):
    def test_snake_case(self):
        self.assertEqual(PolyglotSearch.normalize_name("get_user_name"), "getusername")

    def test_camel_case(self):
        self.assertEqual(PolyglotSearch.normalize_name("getUserName"), "getusername")

    def test_pascal_case(self):
        self.assertEqual(PolyglotSearch.normalize_name("GetUserName"), "getusername")

    def test_already_lower(self):
        self.assertEqual(PolyglotSearch.normalize_name("simple"), "simple")

    def test_with_hyphens(self):
        self.assertEqual(PolyglotSearch.normalize_name("my-func"), "myfunc")

    def test_empty(self):
        self.assertEqual(PolyglotSearch.normalize_name(""), "")

    def test_acronym(self):
        result = PolyglotSearch.normalize_name("parseJSON")
        self.assertEqual(result, "parsejson")


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.search = PolyglotSearch()
        self.search.add_symbols([
            Symbol(name="getUserName", kind="function", language="javascript", line=1),
            Symbol(name="get_user_name", kind="function", language="python", line=5),
            Symbol(name="SetValue", kind="method", language="go", line=10),
            Symbol(name="process", kind="function", language="rust", line=1),
        ])

    def test_search_normalized(self):
        results = self.search.search("get_user_name")
        names = [s.name for s in results]
        self.assertIn("getUserName", names)
        self.assertIn("get_user_name", names)

    def test_search_camel_case(self):
        results = self.search.search("getUserName")
        self.assertTrue(len(results) >= 2)

    def test_search_with_language_filter(self):
        results = self.search.search("getUserName", language="python")
        self.assertTrue(all(s.language == "python" for s in results))

    def test_search_no_match(self):
        results = self.search.search("nonexistent")
        self.assertEqual(len(results), 0)

    def test_search_partial(self):
        results = self.search.search("user")
        self.assertTrue(len(results) >= 2)

    def test_search_exact(self):
        results = self.search.search("process")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].language, "rust")


class TestSearchByKind(unittest.TestCase):
    def setUp(self):
        self.search = PolyglotSearch()
        self.search.add_symbols([
            Symbol(name="foo", kind="function", language="python"),
            Symbol(name="Bar", kind="class", language="python"),
            Symbol(name="baz", kind="function", language="go"),
            Symbol(name="QUX", kind="variable", language="javascript"),
        ])

    def test_filter_functions(self):
        results = self.search.search_by_kind("function")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(s.kind == "function" for s in results))

    def test_filter_class(self):
        results = self.search.search_by_kind("class")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Bar")

    def test_filter_no_match(self):
        results = self.search.search_by_kind("trait")
        self.assertEqual(len(results), 0)


class TestStats(unittest.TestCase):
    def test_empty(self):
        search = PolyglotSearch()
        self.assertEqual(search.stats(), {})

    def test_counts(self):
        search = PolyglotSearch()
        search.add_symbols([
            Symbol(name="a", kind="function", language="python"),
            Symbol(name="b", kind="function", language="python"),
            Symbol(name="c", kind="function", language="go"),
        ])
        st = search.stats()
        self.assertEqual(st["python"], 2)
        self.assertEqual(st["go"], 1)

    def test_add_symbols_immutable(self):
        search = PolyglotSearch()
        batch1 = [Symbol(name="a", kind="function", language="python")]
        batch2 = [Symbol(name="b", kind="function", language="go")]
        search.add_symbols(batch1)
        search.add_symbols(batch2)
        st = search.stats()
        self.assertEqual(st["python"], 1)
        self.assertEqual(st["go"], 1)


if __name__ == "__main__":
    unittest.main()
