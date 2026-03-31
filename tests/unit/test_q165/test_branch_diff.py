"""Tests for BranchDiffEngine (Q165/Task 938)."""
from __future__ import annotations

import unittest

from lidco.session.branch_manager import Branch
from lidco.session.branch_diff import BranchDiff, BranchDiffEngine


def _branch(bid, conv=None, files=None):
    return Branch(
        branch_id=bid,
        name=bid,
        parent_id=None,
        created_at=0.0,
        conversation=conv or [],
        file_snapshots=files or {},
    )


class TestBranchDiffDataclass(unittest.TestCase):
    def test_fields(self):
        d = BranchDiff("a", "b", ["+ line"], {"f.py": "diff"}, 2)
        self.assertEqual(d.branch_a, "a")
        self.assertEqual(d.branch_b, "b")
        self.assertEqual(d.divergence_point, 2)


class TestFindDivergence(unittest.TestCase):
    def setUp(self):
        self.engine = BranchDiffEngine()

    def test_identical(self):
        conv = [{"role": "user", "content": "hi"}]
        self.assertEqual(self.engine.find_divergence(conv, list(conv)), 1)

    def test_empty(self):
        self.assertEqual(self.engine.find_divergence([], []), 0)

    def test_diverge_at_start(self):
        a = [{"role": "user", "content": "a"}]
        b = [{"role": "user", "content": "b"}]
        self.assertEqual(self.engine.find_divergence(a, b), 0)

    def test_diverge_at_middle(self):
        shared = [{"role": "user", "content": "same"}]
        a = shared + [{"role": "assistant", "content": "x"}]
        b = shared + [{"role": "assistant", "content": "y"}]
        self.assertEqual(self.engine.find_divergence(a, b), 1)

    def test_different_lengths(self):
        a = [{"role": "user", "content": "hi"}]
        b = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ok"}]
        self.assertEqual(self.engine.find_divergence(a, b), 1)


class TestDiffFiles(unittest.TestCase):
    def setUp(self):
        self.engine = BranchDiffEngine()

    def test_no_diff_for_identical(self):
        files = {"a.py": "code"}
        self.assertEqual(self.engine.diff_files(files, dict(files)), {})

    def test_changed_file(self):
        a = {"f.py": "old"}
        b = {"f.py": "new"}
        diffs = self.engine.diff_files(a, b)
        self.assertIn("f.py", diffs)
        self.assertIn("---", diffs["f.py"])

    def test_added_file(self):
        a: dict[str, str] = {}
        b = {"new.py": "content"}
        diffs = self.engine.diff_files(a, b)
        self.assertIn("new.py", diffs)

    def test_removed_file(self):
        a = {"old.py": "content"}
        b: dict[str, str] = {}
        diffs = self.engine.diff_files(a, b)
        self.assertIn("old.py", diffs)


class TestDiff(unittest.TestCase):
    def setUp(self):
        self.engine = BranchDiffEngine()

    def test_full_diff(self):
        shared = [{"role": "user", "content": "hello"}]
        ba = _branch("a", shared + [{"role": "assistant", "content": "x"}], {"f.py": "a"})
        bb = _branch("b", shared + [{"role": "assistant", "content": "y"}], {"f.py": "b"})
        result = self.engine.diff(ba, bb)
        self.assertIsInstance(result, BranchDiff)
        self.assertEqual(result.divergence_point, 1)
        self.assertIn("f.py", result.file_diffs)

    def test_identical_branches(self):
        conv = [{"role": "user", "content": "hi"}]
        ba = _branch("a", conv, {"f.py": "same"})
        bb = _branch("b", list(conv), {"f.py": "same"})
        result = self.engine.diff(ba, bb)
        self.assertEqual(len(result.file_diffs), 0)


if __name__ == "__main__":
    unittest.main()
