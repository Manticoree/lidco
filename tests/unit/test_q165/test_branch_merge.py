"""Tests for BranchMerger (Q165/Task 939)."""
from __future__ import annotations

import unittest

from lidco.session.branch_manager import Branch
from lidco.session.branch_merge import MergeResult, BranchMerger


def _branch(bid, conv=None, files=None):
    return Branch(
        branch_id=bid,
        name=bid,
        parent_id=None,
        created_at=0.0,
        conversation=conv or [],
        file_snapshots=files or {},
    )


class TestMergeResultDataclass(unittest.TestCase):
    def test_fields(self):
        r = MergeResult(True, [{"role": "user", "content": "hi"}], {"f": "c"}, [])
        self.assertTrue(r.success)
        self.assertEqual(len(r.merged_conversation), 1)
        self.assertEqual(r.conflicts, [])


class TestBranchMerger(unittest.TestCase):
    def setUp(self):
        self.merger = BranchMerger()

    def test_merge_identical(self):
        conv = [{"role": "user", "content": "hi"}]
        a = _branch("a", list(conv), {"f.py": "x"})
        b = _branch("b", list(conv), {"f.py": "x"})
        result = self.merger.merge(a, b)
        self.assertTrue(result.success)
        self.assertEqual(len(result.conflicts), 0)

    def test_merge_appends_source_after_divergence(self):
        shared = [{"role": "user", "content": "start"}]
        source = _branch("s", shared + [{"role": "assistant", "content": "src_msg"}], {})
        target = _branch("t", shared + [{"role": "assistant", "content": "tgt_msg"}], {})
        result = self.merger.merge(source, target)
        # Target conv + source extra after divergence point (1)
        self.assertEqual(len(result.merged_conversation), 3)

    def test_source_only_file_added(self):
        a = _branch("a", [], {"new.py": "code"})
        b = _branch("b", [], {})
        result = self.merger.merge(a, b)
        self.assertIn("new.py", result.merged_files)
        self.assertTrue(result.success)

    def test_target_only_file_kept(self):
        a = _branch("a", [], {})
        b = _branch("b", [], {"keep.py": "code"})
        result = self.merger.merge(a, b)
        self.assertIn("keep.py", result.merged_files)

    def test_conflict_when_both_changed(self):
        a = _branch("a", [], {"f.py": "version_a"})
        b = _branch("b", [], {"f.py": "version_b"})
        result = self.merger.merge(a, b)
        self.assertFalse(result.success)
        self.assertIn("f.py", result.conflicts)
        # Source wins in merged output
        self.assertEqual(result.merged_files["f.py"], "version_a")

    def test_no_conflict_when_same_content(self):
        a = _branch("a", [], {"f.py": "same"})
        b = _branch("b", [], {"f.py": "same"})
        result = self.merger.merge(a, b)
        self.assertTrue(result.success)
        self.assertEqual(len(result.conflicts), 0)

    def test_multiple_files_mixed(self):
        a = _branch("a", [], {"shared.py": "v_a", "only_a.py": "a", "same.py": "same"})
        b = _branch("b", [], {"shared.py": "v_b", "only_b.py": "b", "same.py": "same"})
        result = self.merger.merge(a, b)
        self.assertIn("shared.py", result.conflicts)
        self.assertIn("only_a.py", result.merged_files)
        self.assertIn("only_b.py", result.merged_files)
        self.assertIn("same.py", result.merged_files)


if __name__ == "__main__":
    unittest.main()
