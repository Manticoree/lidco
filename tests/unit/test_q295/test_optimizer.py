"""Tests for QueryOptimizer2."""
from __future__ import annotations

import unittest

from lidco.database.optimizer import AnalysisResult, IndexSuggestion, QueryOptimizer2


class TestQueryOptimizer2Analyze(unittest.TestCase):
    def setUp(self):
        self.opt = QueryOptimizer2()

    def test_select_star_issue(self):
        result = self.opt.analyze("SELECT * FROM users")
        self.assertTrue(any("SELECT *" in i for i in result.issues))

    def test_delete_without_where(self):
        result = self.opt.analyze("DELETE FROM users")
        self.assertTrue(any("WHERE" in i for i in result.issues))

    def test_update_without_where(self):
        result = self.opt.analyze("UPDATE users SET name = 'x'")
        self.assertTrue(any("WHERE" in i for i in result.issues))

    def test_leading_wildcard_like(self):
        result = self.opt.analyze("SELECT id FROM users WHERE name LIKE '%test'")
        self.assertTrue(any("wildcard" in i for i in result.issues))

    def test_subquery_detected(self):
        sql = "SELECT * FROM orders WHERE user_id IN (SELECT id FROM users)"
        result = self.opt.analyze(sql)
        self.assertTrue(any("subquery" in i.lower() for i in result.issues))

    def test_clean_query_no_issues(self):
        result = self.opt.analyze("SELECT id, name FROM users WHERE id = 1")
        self.assertEqual(len(result.issues), 0)

    def test_order_by_without_limit_suggestion(self):
        result = self.opt.analyze("SELECT id FROM users ORDER BY name")
        self.assertTrue(any("LIMIT" in s for s in result.suggestions))

    def test_index_coverage_detected(self):
        self.opt.add_index("users", ["id"])
        result = self.opt.analyze("SELECT name FROM users WHERE id = 1")
        self.assertTrue(result.uses_index)

    def test_no_index_coverage(self):
        result = self.opt.analyze("SELECT name FROM users WHERE id = 1")
        self.assertFalse(result.uses_index)

    def test_returns_analysis_result(self):
        result = self.opt.analyze("SELECT 1")
        self.assertIsInstance(result, AnalysisResult)


class TestQueryOptimizer2SuggestIndexes(unittest.TestCase):
    def setUp(self):
        self.opt = QueryOptimizer2()

    def test_suggest_where_column(self):
        suggestions = self.opt.suggest_indexes("SELECT * FROM users WHERE email = 'x'")
        self.assertTrue(any(s.columns == ["email"] for s in suggestions))

    def test_suggest_join_column(self):
        sql = "SELECT * FROM orders JOIN users ON orders.user_id = users.id"
        suggestions = self.opt.suggest_indexes(sql)
        cols = [c for s in suggestions for c in s.columns]
        self.assertIn("user_id", cols)

    def test_suggest_order_column(self):
        suggestions = self.opt.suggest_indexes("SELECT id FROM users ORDER BY created_at")
        cols = [c for s in suggestions for c in s.columns]
        self.assertIn("created_at", cols)

    def test_no_suggestions_when_indexed(self):
        self.opt.add_index("users", ["email"])
        suggestions = self.opt.suggest_indexes("SELECT * FROM users WHERE email = 'x'")
        email_suggestions = [s for s in suggestions if "email" in s.columns]
        self.assertEqual(len(email_suggestions), 0)

    def test_returns_index_suggestion_type(self):
        suggestions = self.opt.suggest_indexes("SELECT * FROM users WHERE id = 1")
        for s in suggestions:
            self.assertIsInstance(s, IndexSuggestion)


class TestQueryOptimizer2Rewrite(unittest.TestCase):
    def setUp(self):
        self.opt = QueryOptimizer2()

    def test_rewrite_adds_limit(self):
        result = self.opt.rewrite("SELECT id FROM users ORDER BY name")
        self.assertIn("LIMIT", result)

    def test_rewrite_select_star_comment(self):
        result = self.opt.rewrite("SELECT * FROM users")
        self.assertIn("specify columns", result)

    def test_rewrite_subquery_comment(self):
        sql = "SELECT * FROM orders WHERE user_id IN (SELECT id FROM users)"
        result = self.opt.rewrite(sql)
        self.assertIn("JOIN", result)


class TestQueryOptimizer2Explain(unittest.TestCase):
    def setUp(self):
        self.opt = QueryOptimizer2()

    def test_explain_returns_dict(self):
        result = self.opt.explain("SELECT * FROM users")
        self.assertIsInstance(result, dict)
        self.assertIn("tables", result)
        self.assertIn("scan_type", result)

    def test_full_scan_without_index(self):
        result = self.opt.explain("SELECT * FROM users WHERE id = 1")
        self.assertEqual(result["scan_type"], "full_scan")

    def test_index_scan_with_index(self):
        self.opt.add_index("users", ["id"])
        result = self.opt.explain("SELECT * FROM users WHERE id = 1")
        self.assertEqual(result["scan_type"], "index_scan")

    def test_explain_detects_join(self):
        result = self.opt.explain("SELECT * FROM orders JOIN users ON orders.uid = users.id")
        self.assertTrue(result["has_join"])

    def test_explain_detects_sort(self):
        result = self.opt.explain("SELECT * FROM users ORDER BY name")
        self.assertTrue(result["has_sort"])

    def test_explain_detects_group(self):
        result = self.opt.explain("SELECT count(*) FROM users GROUP BY status")
        self.assertTrue(result["has_group"])


if __name__ == "__main__":
    unittest.main()
