"""Tests for ExplorationMerger."""
from __future__ import annotations

import unittest

from lidco.explore.merger import ExplorationMerger, MergeRecord, MergeResult


SAMPLE_DIFF = """\
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,4 @@
 import os
+import sys

 def hello():
     pass
--- a/src/bar.py
+++ b/src/bar.py
@@ -1 +1,2 @@
 x = 1
+y = 2
"""


class TestExplorationMerger(unittest.TestCase):
    def setUp(self) -> None:
        self.merger = ExplorationMerger()

    def test_plan_merge_extracts_files(self) -> None:
        files = self.merger.plan_merge(SAMPLE_DIFF)
        self.assertEqual(files, ["src/foo.py", "src/bar.py"])

    def test_plan_merge_empty_diff(self) -> None:
        files = self.merger.plan_merge("")
        self.assertEqual(files, [])

    def test_plan_merge_skips_dev_null(self) -> None:
        diff = "+++ /dev/null\n"
        files = self.merger.plan_merge(diff)
        self.assertEqual(files, [])

    def test_plan_merge_strips_b_prefix(self) -> None:
        diff = "+++ b/src/module.py\n"
        files = self.merger.plan_merge(diff)
        self.assertEqual(files, ["src/module.py"])

    def test_apply_merge(self) -> None:
        result = self.merger.apply_merge("exp1", "v1", SAMPLE_DIFF, "balanced", 0.85)
        self.assertTrue(result.success)
        self.assertEqual(result.variant_id, "v1")
        self.assertEqual(len(result.files_applied), 2)
        self.assertEqual(result.conflicts, [])
        self.assertIn("v1", result.message)

    def test_apply_merge_records_history(self) -> None:
        self.merger.apply_merge("exp1", "v1", SAMPLE_DIFF, "balanced", 0.85)
        history = self.merger.history
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].exploration_id, "exp1")
        self.assertEqual(history[0].variant_id, "v1")
        self.assertEqual(history[0].strategy, "balanced")
        self.assertAlmostEqual(history[0].score, 0.85)

    def test_apply_merge_rationale(self) -> None:
        self.merger.apply_merge("exp1", "v1", SAMPLE_DIFF, score=0.9)
        record = self.merger.history[0]
        self.assertIn("0.90", record.rationale)

    def test_dry_run(self) -> None:
        result = self.merger.dry_run(SAMPLE_DIFF)
        self.assertTrue(result.success)
        self.assertEqual(result.variant_id, "dry-run")
        self.assertEqual(len(result.files_applied), 2)
        self.assertIn("Dry run", result.message)

    def test_dry_run_does_not_record_history(self) -> None:
        self.merger.dry_run(SAMPLE_DIFF)
        self.assertEqual(len(self.merger.history), 0)

    def test_get_history_empty(self) -> None:
        self.assertEqual(self.merger.get_history(), [])

    def test_get_history_all(self) -> None:
        self.merger.apply_merge("exp1", "v1", SAMPLE_DIFF)
        self.merger.apply_merge("exp2", "v2", SAMPLE_DIFF)
        self.assertEqual(len(self.merger.get_history()), 2)

    def test_get_history_filtered(self) -> None:
        self.merger.apply_merge("exp1", "v1", SAMPLE_DIFF)
        self.merger.apply_merge("exp2", "v2", SAMPLE_DIFF)
        filtered = self.merger.get_history("exp1")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].exploration_id, "exp1")

    def test_history_immutable(self) -> None:
        self.merger.apply_merge("exp1", "v1", SAMPLE_DIFF)
        h1 = self.merger.history
        h1.append(MergeRecord("x", "y", "z", 0.0, "test"))
        self.assertEqual(len(self.merger.history), 1)

    def test_merge_result_fields(self) -> None:
        result = MergeResult(
            success=True,
            variant_id="v1",
            files_applied=["a.py"],
            conflicts=["b.py"],
            message="ok",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.variant_id, "v1")
        self.assertEqual(result.files_applied, ["a.py"])
        self.assertEqual(result.conflicts, ["b.py"])
        self.assertIsInstance(result.timestamp, float)

    def test_multiple_merges_accumulate(self) -> None:
        self.merger.apply_merge("exp1", "v1", SAMPLE_DIFF)
        self.merger.apply_merge("exp1", "v2", SAMPLE_DIFF)
        self.assertEqual(len(self.merger.get_history("exp1")), 2)


if __name__ == "__main__":
    unittest.main()
