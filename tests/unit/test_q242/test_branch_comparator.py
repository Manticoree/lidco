"""Tests for lidco.conversation.branch_comparator — BranchComparator."""
from __future__ import annotations

import unittest

from lidco.conversation.branch_tree import BranchTree
from lidco.conversation.branch_comparator import BranchComparator, BranchDiff


class TestBranchComparator(unittest.TestCase):
    def setUp(self):
        self.tree = BranchTree()
        self.root = self.tree.add_branch(None, [{"role": "user", "content": "root"}])
        self.a = self.tree.add_branch(self.root, [{"role": "assistant", "content": "branch A"}])
        self.b = self.tree.add_branch(self.root, [{"role": "assistant", "content": "branch B"}])
        self.cmp = BranchComparator(self.tree)

    def test_find_divergence(self):
        d = self.cmp.find_divergence(self.a, self.b)
        self.assertEqual(d, self.root)

    def test_find_divergence_same_branch(self):
        d = self.cmp.find_divergence(self.a, self.a)
        self.assertEqual(d, self.a)

    def test_diff_basic(self):
        diff = self.cmp.diff(self.a, self.b)
        self.assertIsInstance(diff, BranchDiff)
        self.assertEqual(diff.divergence_point, self.root)
        self.assertGreater(len(diff.unique_a), 0)
        self.assertGreater(len(diff.unique_b), 0)

    def test_diff_nonexistent(self):
        diff = self.cmp.diff(self.a, "nope")
        self.assertIsNone(diff.divergence_point)

    def test_cost_comparison(self):
        cost = self.cmp.cost_comparison(self.a, self.b)
        self.assertEqual(cost["message_count_a"], 1)
        self.assertEqual(cost["message_count_b"], 1)
        self.assertGreater(cost["content_length_a"], 0)

    def test_cost_nonexistent(self):
        cost = self.cmp.cost_comparison("nope", self.b)
        self.assertEqual(cost["message_count_a"], 0)

    def test_similarity_identical(self):
        c = self.tree.add_branch(self.root, [{"role": "assistant", "content": "branch A"}])
        sim = self.cmp.similarity(self.a, c)
        self.assertAlmostEqual(sim, 1.0)

    def test_similarity_different(self):
        sim = self.cmp.similarity(self.a, self.b)
        self.assertLess(sim, 1.0)

    def test_similarity_nonexistent(self):
        self.assertEqual(self.cmp.similarity("nope", self.b), 0.0)

    def test_similarity_empty_branches(self):
        e1 = self.tree.add_branch(self.root, [])
        e2 = self.tree.add_branch(self.root, [])
        self.assertAlmostEqual(self.cmp.similarity(e1, e2), 1.0)


if __name__ == "__main__":
    unittest.main()
