"""Tests for DocSearchEngine (Q258)."""
from __future__ import annotations

import unittest

from lidco.docgen.search_engine import DocSearchEngine, SearchResult


class TestSearchResult(unittest.TestCase):
    def test_dataclass_fields(self):
        r = SearchResult(title="T", snippet="S", score=1.5, source="f.py")
        self.assertEqual(r.title, "T")
        self.assertEqual(r.snippet, "S")
        self.assertEqual(r.score, 1.5)
        self.assertEqual(r.source, "f.py")

    def test_frozen(self):
        r = SearchResult(title="T", snippet="S", score=1.0)
        with self.assertRaises(AttributeError):
            r.title = "X"  # type: ignore[misc]

    def test_default_source(self):
        r = SearchResult(title="T", snippet="S", score=0.0)
        self.assertEqual(r.source, "")


class TestIndex(unittest.TestCase):
    def setUp(self):
        self.engine = DocSearchEngine()

    def test_index_single(self):
        self.engine.index("Title", "Content here")
        self.assertEqual(self.engine.stats()["indexed_count"], 1)

    def test_index_multiple(self):
        self.engine.index("A", "Alpha")
        self.engine.index("B", "Beta")
        self.assertEqual(self.engine.stats()["indexed_count"], 2)

    def test_index_with_source(self):
        self.engine.index("Module docs", "Documentation for the module", source="mod.py")
        results = self.engine.search("documentation module")
        self.assertTrue(len(results) > 0)


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.engine = DocSearchEngine()
        self.engine.index("Python Guide", "Python is a programming language with dynamic typing")
        self.engine.index("Java Basics", "Java is a statically typed programming language")
        self.engine.index("Rust Manual", "Rust focuses on safety and performance")

    def test_basic_search(self):
        results = self.engine.search("python")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].title, "Python Guide")

    def test_search_limit(self):
        results = self.engine.search("programming", limit=1)
        self.assertEqual(len(results), 1)

    def test_no_results(self):
        results = self.engine.search("nonexistent_xyz_term")
        self.assertEqual(results, [])

    def test_empty_query(self):
        results = self.engine.search("")
        self.assertEqual(results, [])

    def test_multiple_matches(self):
        results = self.engine.search("programming language")
        self.assertTrue(len(results) >= 2)

    def test_score_ordering(self):
        results = self.engine.search("python programming")
        if len(results) >= 2:
            self.assertGreaterEqual(results[0].score, results[1].score)

    def test_snippet_present(self):
        results = self.engine.search("rust")
        self.assertTrue(len(results) > 0)
        self.assertTrue(len(results[0].snippet) > 0)

    def test_empty_index(self):
        engine = DocSearchEngine()
        results = engine.search("anything")
        self.assertEqual(results, [])

    def test_score_is_float(self):
        results = self.engine.search("python")
        self.assertIsInstance(results[0].score, float)


class TestClear(unittest.TestCase):
    def test_clear(self):
        engine = DocSearchEngine()
        engine.index("A", "Alpha")
        engine.index("B", "Beta")
        engine.clear()
        self.assertEqual(engine.stats()["indexed_count"], 0)
        self.assertEqual(engine.stats()["total_terms"], 0)

    def test_search_after_clear(self):
        engine = DocSearchEngine()
        engine.index("A", "Alpha")
        engine.clear()
        results = engine.search("alpha")
        self.assertEqual(results, [])


class TestStats(unittest.TestCase):
    def test_empty_stats(self):
        engine = DocSearchEngine()
        s = engine.stats()
        self.assertEqual(s["indexed_count"], 0)
        self.assertEqual(s["total_terms"], 0)

    def test_stats_after_indexing(self):
        engine = DocSearchEngine()
        engine.index("Hello World", "Some content about testing")
        s = engine.stats()
        self.assertEqual(s["indexed_count"], 1)
        self.assertGreater(s["total_terms"], 0)

    def test_stats_keys(self):
        engine = DocSearchEngine()
        s = engine.stats()
        self.assertIn("indexed_count", s)
        self.assertIn("total_terms", s)


if __name__ == "__main__":
    unittest.main()
