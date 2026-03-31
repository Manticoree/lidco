"""Tests for DiffStatsCollector."""
from __future__ import annotations

import unittest

from lidco.merge.diff_stats import DiffStatsCollector, FileDiffStats


class TestFileDiffStats(unittest.TestCase):
    def test_dataclass_fields(self):
        s = FileDiffStats(file_path="a.py", additions=5, deletions=3, changes=2, similarity=0.8)
        self.assertEqual(s.file_path, "a.py")
        self.assertEqual(s.additions, 5)
        self.assertEqual(s.deletions, 3)
        self.assertEqual(s.changes, 2)
        self.assertAlmostEqual(s.similarity, 0.8)


class TestDiffStatsCollector(unittest.TestCase):
    def setUp(self):
        self.c = DiffStatsCollector()

    def test_compute_identical(self):
        text = "a\nb\nc\n"
        s = self.c.compute(text, text, "f.py")
        self.assertEqual(s.additions, 0)
        self.assertEqual(s.deletions, 0)
        self.assertAlmostEqual(s.similarity, 1.0)

    def test_compute_all_new(self):
        s = self.c.compute("", "a\nb\n", "f.py")
        self.assertEqual(s.additions, 2)
        self.assertEqual(s.deletions, 0)

    def test_compute_all_deleted(self):
        s = self.c.compute("a\nb\n", "", "f.py")
        self.assertEqual(s.additions, 0)
        self.assertEqual(s.deletions, 2)

    def test_compute_replacement(self):
        s = self.c.compute("a\n", "b\n", "f.py")
        self.assertGreater(s.additions, 0)
        self.assertGreater(s.deletions, 0)

    def test_compute_default_path(self):
        s = self.c.compute("a\n", "b\n")
        self.assertEqual(s.file_path, "")

    def test_compute_similarity_range(self):
        s = self.c.compute("a\nb\nc\n", "a\nb\nd\n", "f.py")
        self.assertGreaterEqual(s.similarity, 0.0)
        self.assertLessEqual(s.similarity, 1.0)

    def test_compute_changes_count(self):
        s = self.c.compute("a\nb\n", "a\nX\n", "f.py")
        self.assertGreaterEqual(s.changes, 1)

    def test_compute_batch(self):
        diffs = [
            ("a.py", "old\n", "new\n"),
            ("b.py", "x\n", "x\n"),
        ]
        results = self.c.compute_batch(diffs)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].file_path, "a.py")
        self.assertEqual(results[1].file_path, "b.py")

    def test_compute_batch_empty(self):
        results = self.c.compute_batch([])
        self.assertEqual(results, [])

    def test_summary_totals(self):
        stats = [
            FileDiffStats("a.py", additions=3, deletions=1, changes=1, similarity=0.9),
            FileDiffStats("b.py", additions=2, deletions=0, changes=0, similarity=1.0),
        ]
        s = self.c.summary(stats)
        self.assertEqual(s["total_additions"], 5)
        self.assertEqual(s["total_deletions"], 1)
        self.assertEqual(s["files_changed"], 2)

    def test_summary_no_changes(self):
        stats = [FileDiffStats("c.py", 0, 0, 0, 1.0)]
        s = self.c.summary(stats)
        self.assertEqual(s["files_changed"], 0)

    def test_format_stat_line_additions(self):
        s = FileDiffStats("f.py", additions=10, deletions=0, changes=0, similarity=0.9)
        line = self.c.format_stat_line(s)
        self.assertIn("f.py", line)
        self.assertIn("10 ++", line)

    def test_format_stat_line_deletions(self):
        s = FileDiffStats("f.py", additions=0, deletions=3, changes=0, similarity=0.9)
        line = self.c.format_stat_line(s)
        self.assertIn("3 --", line)

    def test_format_stat_line_both(self):
        s = FileDiffStats("f.py", additions=5, deletions=2, changes=1, similarity=0.8)
        line = self.c.format_stat_line(s)
        self.assertIn("5 ++", line)
        self.assertIn("2 --", line)

    def test_format_stat_line_no_changes(self):
        s = FileDiffStats("f.py", 0, 0, 0, 1.0)
        line = self.c.format_stat_line(s)
        self.assertIn("no changes", line)

    def test_format_stat_line_unknown_path(self):
        s = FileDiffStats("", 1, 0, 0, 0.9)
        line = self.c.format_stat_line(s)
        self.assertIn("(unknown)", line)

    def test_format_summary(self):
        stats = [
            FileDiffStats("a.py", 3, 1, 1, 0.9),
            FileDiffStats("b.py", 2, 0, 0, 1.0),
        ]
        out = self.c.format_summary(stats)
        self.assertIn("file(s) changed", out)
        self.assertIn("insertion(s)(+)", out)
        self.assertIn("deletion(s)(-)", out)

    def test_format_summary_empty(self):
        out = self.c.format_summary([])
        self.assertIn("0 file(s) changed", out)

    def test_compute_empty_both(self):
        s = self.c.compute("", "")
        self.assertEqual(s.additions, 0)
        self.assertEqual(s.deletions, 0)
        self.assertAlmostEqual(s.similarity, 1.0)


if __name__ == "__main__":
    unittest.main()
