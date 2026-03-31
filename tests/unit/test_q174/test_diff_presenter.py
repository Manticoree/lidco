"""Tests for DiffPresenter."""
from __future__ import annotations

import unittest

from lidco.explore.diff_presenter import DiffPresenter, DiffSummary


SAMPLE_DIFF = """\
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,5 @@
 import os
+import sys
+import json

 def hello():
-    pass
+    print("hello")
"""


class TestDiffPresenter(unittest.TestCase):
    def setUp(self) -> None:
        self.presenter = DiffPresenter()

    def test_summarize_variant_basic(self) -> None:
        summary = self.presenter.summarize_variant("v1", "balanced", SAMPLE_DIFF, score=0.8)
        self.assertEqual(summary.variant_id, "v1")
        self.assertEqual(summary.strategy, "balanced")
        self.assertEqual(summary.score, 0.8)
        self.assertEqual(summary.status, "completed")

    def test_summarize_variant_empty_diff(self) -> None:
        summary = self.presenter.summarize_variant("v1", "conservative", "")
        self.assertEqual(summary.lines_added, 0)
        self.assertEqual(summary.lines_removed, 0)
        self.assertEqual(summary.files_changed, 0)

    def test_summarize_counts_additions_removals(self) -> None:
        summary = self.presenter.summarize_variant("v1", "balanced", SAMPLE_DIFF)
        self.assertEqual(summary.lines_added, 3)  # +import sys, +import json, +print
        self.assertEqual(summary.lines_removed, 1)  # -pass

    def test_summarize_counts_files(self) -> None:
        summary = self.presenter.summarize_variant("v1", "balanced", SAMPLE_DIFF)
        self.assertGreaterEqual(summary.files_changed, 1)

    def test_summarize_custom_status(self) -> None:
        summary = self.presenter.summarize_variant("v1", "aggressive", "", status="failed")
        self.assertEqual(summary.status, "failed")

    def test_format_comparison_table(self) -> None:
        summaries = [
            DiffSummary("v1", "conservative", 5, 2, 1, 0.8, "completed"),
            DiffSummary("v2", "aggressive", 20, 10, 3, 0.6, "completed"),
        ]
        table = self.presenter.format_comparison_table(summaries)
        self.assertIn("Strategy", table)
        self.assertIn("conservative", table)
        self.assertIn("aggressive", table)
        self.assertIn("0.80", table)
        self.assertIn("0.60", table)

    def test_format_comparison_table_empty(self) -> None:
        result = self.presenter.format_comparison_table([])
        self.assertEqual(result, "No variants to compare.")

    def test_format_comparison_table_has_header(self) -> None:
        summaries = [DiffSummary("v1", "balanced", 1, 0, 1, 0.5, "completed")]
        table = self.presenter.format_comparison_table(summaries)
        lines = table.split("\n")
        self.assertGreaterEqual(len(lines), 3)  # header + separator + row
        self.assertIn("|", lines[0])

    def test_format_diff_comparison(self) -> None:
        result = self.presenter.format_diff_comparison("diff A", "diff B", "v1", "v2")
        self.assertIn("=== Variant v1 ===", result)
        self.assertIn("=== Variant v2 ===", result)
        self.assertIn("diff A", result)
        self.assertIn("diff B", result)

    def test_format_diff_comparison_empty_diffs(self) -> None:
        result = self.presenter.format_diff_comparison("", "")
        self.assertIn("(no changes)", result)

    def test_format_diff_comparison_default_labels(self) -> None:
        result = self.presenter.format_diff_comparison("x", "y")
        self.assertIn("Variant A", result)
        self.assertIn("Variant B", result)

    def test_format_winner_announcement(self) -> None:
        summary = DiffSummary("v1", "balanced", 10, 3, 2, 0.85, "completed")
        text = self.presenter.format_winner_announcement(summary)
        self.assertIn("Winner", text)
        self.assertIn("v1", text)
        self.assertIn("balanced", text)
        self.assertIn("0.85", text)
        self.assertIn("+10/-3", text)
        self.assertIn("2 files", text)

    def test_summarize_skips_dev_null(self) -> None:
        diff = """\
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,2 @@
+line1
+line2
"""
        summary = self.presenter.summarize_variant("v1", "creative", diff)
        self.assertEqual(summary.lines_added, 2)
        # /dev/null should not be counted as a changed file
        # b/new_file.py from +++ line should be counted
        self.assertGreaterEqual(summary.files_changed, 1)

    def test_format_comparison_table_row_numbering(self) -> None:
        summaries = [
            DiffSummary("v1", "a", 1, 1, 1, 0.5, "completed"),
            DiffSummary("v2", "b", 2, 2, 2, 0.4, "completed"),
            DiffSummary("v3", "c", 3, 3, 3, 0.3, "completed"),
        ]
        table = self.presenter.format_comparison_table(summaries)
        self.assertIn("| 1 |", table)
        self.assertIn("| 2 |", table)
        self.assertIn("| 3 |", table)


if __name__ == "__main__":
    unittest.main()
