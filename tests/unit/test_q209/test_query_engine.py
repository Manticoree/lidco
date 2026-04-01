"""Tests for query_engine module."""
from __future__ import annotations

import unittest

from lidco.understanding.semantic_search import SemanticSearchIndex
from lidco.understanding.query_engine import CodeQueryEngine, CodeQueryResult


class TestCodeQueryResult(unittest.TestCase):
    def test_frozen(self):
        r = CodeQueryResult()
        with self.assertRaises(AttributeError):
            r.total = 5  # type: ignore[misc]

    def test_defaults(self):
        r = CodeQueryResult()
        self.assertEqual(r.matches, ())
        self.assertEqual(r.query, "")
        self.assertEqual(r.total, 0)


class TestCodeQueryEngine(unittest.TestCase):
    def setUp(self):
        self.idx = SemanticSearchIndex()
        self.idx.add_document("auth.py", "authenticate", "authenticate validate credentials password login")
        self.idx.add_document("db.py", "connect_db", "database connection pool query execute")
        self.engine = CodeQueryEngine(search_index=self.idx)

    def test_query_returns_results(self):
        result = self.engine.query("authenticate credentials login")
        self.assertIsInstance(result, CodeQueryResult)
        self.assertGreater(result.total, 0)

    def test_query_empty(self):
        engine = CodeQueryEngine()
        result = engine.query("anything")
        self.assertEqual(result.total, 0)

    def test_parse_query_extracts_kind(self):
        parsed = self.engine.parse_query("find the function that authenticates")
        self.assertEqual(parsed["kind"], "function")

    def test_parse_query_extracts_name_pattern(self):
        parsed = self.engine.parse_query('find "connect_db"')
        self.assertEqual(parsed["name_pattern"], "connect_db")

    def test_parse_query_snake_case_detection(self):
        parsed = self.engine.parse_query("where is connect_db used")
        self.assertEqual(parsed["name_pattern"], "connect_db")

    def test_explain(self):
        explanation = self.engine.explain("find function authenticate")
        self.assertIn("Query:", explanation)
        self.assertIn("Target kind:", explanation)

    def test_history(self):
        self.engine.query("first query")
        self.engine.query("second query")
        h = self.engine.history()
        self.assertEqual(len(h), 2)
        self.assertEqual(h[0], "first query")
        self.assertEqual(h[1], "second query")

    def test_clear_history(self):
        self.engine.query("some query")
        self.engine.clear_history()
        self.assertEqual(self.engine.history(), [])


if __name__ == "__main__":
    unittest.main()
