"""Tests for AnnotationSearch."""
from __future__ import annotations

import json
import unittest

from lidco.annotations.engine import AnnotationEngine
from lidco.annotations.search import AnnotationSearch, SearchResult


class TestSearchResult(unittest.TestCase):
    def test_defaults(self):
        from lidco.annotations.engine import Annotation
        a = Annotation(id="x", file_path="f.py", line=1, text="hi")
        sr = SearchResult(annotation=a)
        self.assertEqual(sr.relevance, 1.0)


class TestAnnotationSearch(unittest.TestCase):
    def setUp(self):
        self.engine = AnnotationEngine()
        self.search = AnnotationSearch(self.engine)

    def test_search_empty(self):
        self.assertEqual(self.search.search("anything"), [])

    def test_search_match(self):
        self.engine.add("f.py", 1, "fix the bug")
        self.engine.add("f.py", 2, "add feature")
        results = self.search.search("bug")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].annotation.text, "fix the bug")

    def test_search_limit(self):
        for i in range(10):
            self.engine.add("f.py", i, f"item {i}")
        results = self.search.search("item", limit=3)
        self.assertEqual(len(results), 3)

    def test_by_file(self):
        self.engine.add("a.py", 1, "x")
        self.engine.add("b.py", 1, "y")
        grouped = self.search.by_file()
        self.assertIn("a.py", grouped)
        self.assertIn("b.py", grouped)

    def test_by_category(self):
        self.engine.add("f.py", 1, "x", category="warning")
        self.engine.add("f.py", 2, "y", category="note")
        grouped = self.search.by_category()
        self.assertIn("warning", grouped)
        self.assertIn("note", grouped)

    def test_by_author(self):
        self.engine.add("f.py", 1, "x", author="alice")
        self.engine.add("f.py", 2, "y", author="bob")
        grouped = self.search.by_author()
        self.assertIn("alice", grouped)
        self.assertIn("bob", grouped)

    def test_bulk_remove_by_category(self):
        self.engine.add("f.py", 1, "x", category="warning")
        self.engine.add("f.py", 2, "y", category="note")
        n = self.search.bulk_remove(category="warning")
        self.assertEqual(n, 1)
        self.assertEqual(self.engine.count(), 1)

    def test_bulk_remove_by_file(self):
        self.engine.add("a.py", 1, "x")
        self.engine.add("b.py", 1, "y")
        n = self.search.bulk_remove(file_path="a.py")
        self.assertEqual(n, 1)
        self.assertEqual(self.engine.count(), 1)

    def test_export(self):
        self.engine.add("f.py", 1, "note")
        data = json.loads(self.search.export())
        self.assertEqual(len(data), 1)

    def test_stats(self):
        self.engine.add("a.py", 1, "x", category="warning", author="alice")
        self.engine.add("b.py", 2, "y", category="note", author="bob")
        s = self.search.stats()
        self.assertEqual(s["total"], 2)
        self.assertEqual(len(s["by_file"]), 2)
        self.assertEqual(len(s["by_category"]), 2)
        self.assertEqual(len(s["by_author"]), 2)

    def test_summary(self):
        self.engine.add("f.py", 1, "x")
        s = self.search.summary()
        self.assertEqual(s["total"], 1)
        self.assertEqual(s["files"], 1)


if __name__ == "__main__":
    unittest.main()
