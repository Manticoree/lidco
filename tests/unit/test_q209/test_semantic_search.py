"""Tests for semantic_search module."""
from __future__ import annotations

import unittest

from lidco.understanding.semantic_search import (
    SearchResult,
    SearchScope,
    SemanticSearchIndex,
)


class TestSearchScope(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(SearchScope.FILE, "file")
        self.assertEqual(SearchScope.SYMBOL, "symbol")
        self.assertEqual(SearchScope.SNIPPET, "snippet")


class TestSearchResult(unittest.TestCase):
    def test_frozen(self):
        r = SearchResult(path="a.py", name="foo", score=0.9)
        with self.assertRaises(AttributeError):
            r.score = 0.5  # type: ignore[misc]

    def test_defaults(self):
        r = SearchResult(path="a.py", name="foo", score=0.5)
        self.assertEqual(r.snippet, "")
        self.assertEqual(r.line, 0)
        self.assertEqual(r.scope, SearchScope.SYMBOL)


class TestSemanticSearchIndex(unittest.TestCase):
    def setUp(self):
        self.idx = SemanticSearchIndex()

    def test_add_document_and_count(self):
        self.assertEqual(self.idx.document_count(), 0)
        self.idx.add_document("a.py", "alpha", "def alpha(): pass")
        self.assertEqual(self.idx.document_count(), 1)

    def test_search_returns_results(self):
        self.idx.add_document("a.py", "alpha", "python function alpha beta")
        self.idx.add_document("b.py", "bravo", "javascript class bravo delta")
        results = self.idx.search("python alpha")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].path, "a.py")

    def test_search_ranked_by_score(self):
        self.idx.add_document("a.py", "a", "search query matching terms")
        self.idx.add_document("b.py", "b", "completely unrelated content zebra")
        self.idx.add_document("c.py", "c", "search query matching terms query search")
        results = self.idx.search("search query matching")
        self.assertGreaterEqual(len(results), 2)
        # 'c' has more matching terms so should score higher
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_search_scope_filter(self):
        self.idx.add_document("a.py", "a", "hello world", SearchScope.FILE)
        self.idx.add_document("b.py", "b", "hello world", SearchScope.SNIPPET)
        results = self.idx.search("hello world", scope=SearchScope.FILE)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].path, "a.py")

    def test_search_empty_query(self):
        self.idx.add_document("a.py", "a", "content")
        results = self.idx.search("")
        self.assertEqual(results, [])

    def test_search_empty_index(self):
        results = self.idx.search("anything")
        self.assertEqual(results, [])

    def test_tokenize_filters_stopwords(self):
        tokens = self.idx._tokenize("the quick brown fox is a test")
        self.assertNotIn("the", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("a", tokens)
        self.assertIn("quick", tokens)
        self.assertIn("brown", tokens)

    def test_clear(self):
        self.idx.add_document("a.py", "a", "content")
        self.idx.clear()
        self.assertEqual(self.idx.document_count(), 0)

    def test_remove_document_existing(self):
        self.idx.add_document("a.py", "a", "content")
        result = self.idx.remove_document("a.py")
        self.assertTrue(result)
        self.assertEqual(self.idx.document_count(), 0)

    def test_remove_document_missing(self):
        result = self.idx.remove_document("nonexistent.py")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
