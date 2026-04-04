"""Tests for lidco.githistory.analyzer."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from lidco.githistory.analyzer import CommitRecord, HistoryAnalyzer


class TestCommitRecord(unittest.TestCase):
    def test_immutable(self):
        r = CommitRecord(hash="abc", author="Alice", date=datetime(2026, 1, 1), files=("a.py",), message="init")
        self.assertEqual(r.hash, "abc")
        with self.assertRaises(AttributeError):
            r.hash = "xyz"  # type: ignore[misc]

    def test_fields(self):
        d = datetime(2026, 3, 15)
        r = CommitRecord(hash="h1", author="Bob", date=d, files=("x.py", "y.py"), message="msg")
        self.assertEqual(r.author, "Bob")
        self.assertEqual(r.files, ("x.py", "y.py"))


class TestHistoryAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = HistoryAnalyzer()
        base = datetime(2026, 1, 1)
        self.analyzer.add_commit("a1", "Alice", base, ["f1.py", "f2.py"], "first commit")
        self.analyzer.add_commit("a2", "Bob", base + timedelta(days=1), ["f2.py", "f3.py"], "second")
        self.analyzer.add_commit("a3", "Alice", base + timedelta(days=2), ["f1.py"], "third")
        self.analyzer.add_commit("a4", "Alice", base + timedelta(days=3), ["f1.py", "f4.py"], "fourth")
        self.analyzer.add_commit("a5", "Charlie", base + timedelta(days=4), ["f2.py"], "fifth")

    def test_commit_count(self):
        self.assertEqual(self.analyzer.commit_count, 5)

    def test_add_commit_empty_hash_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.add_commit("", "X", datetime.now(), [], "msg")

    def test_add_commit_empty_author_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.add_commit("h", "", datetime.now(), [], "msg")

    def test_contributor_stats_keys(self):
        stats = self.analyzer.contributor_stats()
        self.assertIn("Alice", stats)
        self.assertIn("Bob", stats)
        self.assertIn("Charlie", stats)

    def test_contributor_stats_commit_count(self):
        stats = self.analyzer.contributor_stats()
        self.assertEqual(stats["Alice"]["commit_count"], 3)
        self.assertEqual(stats["Bob"]["commit_count"], 1)

    def test_contributor_stats_files_touched(self):
        stats = self.analyzer.contributor_stats()
        self.assertIn("f1.py", stats["Alice"]["files_touched"])
        self.assertIn("f4.py", stats["Alice"]["files_touched"])

    def test_file_churn_order(self):
        churn = self.analyzer.file_churn()
        # f1.py appears in 3 commits, f2.py in 3 commits
        files = [f for f, _ in churn]
        self.assertIn("f1.py", files[:2])
        self.assertIn("f2.py", files[:2])

    def test_hotspots_top_n(self):
        spots = self.analyzer.hotspots(2)
        self.assertEqual(len(spots), 2)

    def test_hotspots_default(self):
        spots = self.analyzer.hotspots()
        # We have 4 unique files
        self.assertEqual(len(spots), 4)

    def test_release_cadence(self):
        cad = self.analyzer.release_cadence()
        self.assertEqual(cad["total_commits"], 5)
        self.assertGreater(cad["days_span"], 0)
        self.assertGreater(cad["avg_per_day"], 0)

    def test_release_cadence_empty(self):
        a = HistoryAnalyzer()
        cad = a.release_cadence()
        self.assertEqual(cad["total_commits"], 0)

    def test_summary_keys(self):
        s = self.analyzer.summary()
        self.assertIn("commit_count", s)
        self.assertIn("contributor_count", s)
        self.assertIn("hotspots", s)
        self.assertIn("cadence", s)

    def test_summary_values(self):
        s = self.analyzer.summary()
        self.assertEqual(s["commit_count"], 5)
        self.assertEqual(s["contributor_count"], 3)


if __name__ == "__main__":
    unittest.main()
