"""Tests for lidco.conversation.branch_pruner — BranchPruner."""
from __future__ import annotations

import unittest

from lidco.conversation.branch_tree import BranchTree
from lidco.conversation.branch_pruner import BranchPruner, PruneResult


class TestPruneResult(unittest.TestCase):
    def test_defaults(self):
        r = PruneResult(removed_count=0)
        self.assertEqual(r.removed_count, 0)
        self.assertEqual(r.removed_ids, [])


class TestBranchPruner(unittest.TestCase):
    def setUp(self):
        self.tree = BranchTree()
        self.root = self.tree.add_branch(None, [{"role": "user"}])
        self.c1 = self.tree.add_branch(self.root, [{"role": "assistant", "content": "c1"}])
        self.c2 = self.tree.add_branch(self.root, [{"role": "assistant", "content": "c2"}])
        self.gc1 = self.tree.add_branch(self.c1, [{"role": "user", "content": "gc1"}])
        self.pruner = BranchPruner(self.tree)

    def test_prune_leaf(self):
        result = self.pruner.prune(self.c2)
        self.assertEqual(result.removed_count, 1)
        self.assertIn(self.c2, result.removed_ids)
        self.assertIsNone(self.tree.get_branch(self.c2))

    def test_prune_with_descendants(self):
        result = self.pruner.prune(self.c1)
        self.assertGreaterEqual(result.removed_count, 2)
        self.assertIsNone(self.tree.get_branch(self.c1))
        self.assertIsNone(self.tree.get_branch(self.gc1))

    def test_prune_nonexistent(self):
        result = self.pruner.prune("nope")
        self.assertEqual(result.removed_count, 0)

    def test_prune_dead(self):
        # Add empty branches
        e1 = self.tree.add_branch(self.root, [])
        e2 = self.tree.add_branch(self.root, [])
        result = self.pruner.prune_dead(min_messages=0)
        self.assertGreaterEqual(result.removed_count, 2)
        self.assertIsNone(self.tree.get_branch(e1))
        self.assertIsNone(self.tree.get_branch(e2))

    def test_merge_back(self):
        ok = self.pruner.merge_back(self.c2, self.c1)
        self.assertTrue(ok)
        merged = self.tree.get_branch(self.c1)
        self.assertGreater(len(merged.messages), 1)

    def test_merge_back_nonexistent(self):
        self.assertFalse(self.pruner.merge_back("nope", self.c1))

    def test_archive(self):
        archive = self.pruner.archive(self.c1)
        self.assertIn("branch_id", archive)
        self.assertIn("nodes", archive)
        self.assertIn(self.c1, archive["nodes"])
        self.assertIn(self.gc1, archive["nodes"])

    def test_archive_nonexistent(self):
        self.assertEqual(self.pruner.archive("nope"), {})

    def test_space_savings(self):
        savings = self.pruner.space_savings(self.c1)
        self.assertGreater(savings, 0)

    def test_space_savings_nonexistent(self):
        self.assertEqual(self.pruner.space_savings("nope"), 0)


if __name__ == "__main__":
    unittest.main()
