"""Tests for ChurnAnalyzer, ChurnRecord."""
from __future__ import annotations

import unittest

from lidco.project_analytics.churn_analyzer import (
    ChurnAnalyzer,
    ChurnRecord,
)


class TestChurnRecord(unittest.TestCase):
    def test_frozen(self):
        rec = ChurnRecord(file="a.py")
        with self.assertRaises(AttributeError):
            rec.file = "b.py"  # type: ignore[misc]

    def test_defaults(self):
        rec = ChurnRecord(file="a.py")
        self.assertEqual(rec.change_count, 0)
        self.assertEqual(rec.authors, ())
        self.assertEqual(rec.last_changed, 0.0)


class TestChurnAnalyzer(unittest.TestCase):
    def test_add_change_and_top(self):
        analyzer = ChurnAnalyzer()
        analyzer.add_change("a.py", author="alice", timestamp=100.0)
        analyzer.add_change("a.py", author="bob", timestamp=200.0)
        analyzer.add_change("b.py", author="alice", timestamp=150.0)
        top = analyzer.top_churned(10)
        self.assertEqual(top[0].file, "a.py")
        self.assertEqual(top[0].change_count, 2)

    def test_author_distribution(self):
        analyzer = ChurnAnalyzer()
        analyzer.add_change("a.py", author="alice", timestamp=1.0)
        analyzer.add_change("a.py", author="alice", timestamp=2.0)
        analyzer.add_change("b.py", author="bob", timestamp=3.0)
        dist = analyzer.author_distribution()
        self.assertEqual(dist["alice"], 2)
        self.assertEqual(dist["bob"], 1)

    def test_file_risk_score_no_data(self):
        analyzer = ChurnAnalyzer()
        self.assertEqual(analyzer.file_risk_score("x.py"), 0.0)

    def test_file_risk_score_with_data(self):
        analyzer = ChurnAnalyzer()
        analyzer.add_change("a.py", author="alice", timestamp=1.0)
        analyzer.add_change("a.py", author="bob", timestamp=2.0)
        score = analyzer.file_risk_score("a.py")
        self.assertGreater(score, 0.0)

    def test_summary_empty(self):
        analyzer = ChurnAnalyzer()
        text = analyzer.summary()
        self.assertIn("No churn data", text)

    def test_summary_with_data(self):
        analyzer = ChurnAnalyzer()
        analyzer.add_change("a.py", author="alice", timestamp=1.0)
        analyzer.add_change("b.py", author="bob", timestamp=2.0)
        text = analyzer.summary()
        self.assertIn("Files: 2", text)
        self.assertIn("Total changes: 2", text)

    def test_clear(self):
        analyzer = ChurnAnalyzer()
        analyzer.add_change("a.py", author="alice", timestamp=1.0)
        analyzer.clear()
        self.assertEqual(analyzer.top_churned(), [])

    def test_top_churned_limit(self):
        analyzer = ChurnAnalyzer()
        for i in range(20):
            analyzer.add_change(f"file{i}.py", author="a", timestamp=float(i))
        top = analyzer.top_churned(5)
        self.assertEqual(len(top), 5)
