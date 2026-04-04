"""Tests for lidco.merge.strategy."""
from __future__ import annotations

import unittest

from lidco.merge.strategy import BranchInfo, MergeStrategy, Strategy


class TestStrategyEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Strategy.MERGE.value, "merge")
        self.assertEqual(Strategy.REBASE.value, "rebase")
        self.assertEqual(Strategy.SQUASH.value, "squash")

    def test_all_members(self):
        self.assertEqual(len(Strategy), 3)


class TestBranchInfo(unittest.TestCase):
    def test_defaults(self):
        b = BranchInfo(name="feat")
        self.assertEqual(b.commit_count, 1)
        self.assertFalse(b.has_shared_commits)
        self.assertFalse(b.is_public)
        self.assertEqual(b.authors, [])


class TestMergeStrategy(unittest.TestCase):
    def setUp(self):
        self.ms = MergeStrategy()

    def test_recommend_public_branch(self):
        b = BranchInfo(name="main", is_public=True, commit_count=20)
        self.assertEqual(self.ms.recommend(b), "merge")

    def test_recommend_shared_commits(self):
        b = BranchInfo(name="feat", has_shared_commits=True, commit_count=5)
        self.assertEqual(self.ms.recommend(b), "merge")

    def test_recommend_small_branch(self):
        b = BranchInfo(name="fix", commit_count=1)
        self.assertEqual(self.ms.recommend(b), "squash")

    def test_recommend_medium_solo_branch(self):
        b = BranchInfo(name="feat", commit_count=5, authors=["alice"])
        self.assertEqual(self.ms.recommend(b), "rebase")

    def test_recommend_large_branch(self):
        b = BranchInfo(name="feat", commit_count=50)
        self.assertEqual(self.ms.recommend(b), "merge")

    def test_compare_strategies_keys(self):
        comp = self.ms.compare_strategies()
        self.assertIn("merge", comp)
        self.assertIn("rebase", comp)
        self.assertIn("squash", comp)
        for key in comp:
            self.assertIn("pros", comp[key])
            self.assertIn("cons", comp[key])

    def test_pros_cons_merge(self):
        pc = self.ms.pros_cons("merge")
        self.assertGreater(len(pc["pros"]), 0)
        self.assertGreater(len(pc["cons"]), 0)

    def test_pros_cons_unknown_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.ms.pros_cons("cherry-pick")
        self.assertIn("cherry-pick", str(ctx.exception))

    def test_is_rebase_safe_solo(self):
        b = BranchInfo(name="fix", commit_count=3, authors=["alice"])
        self.assertTrue(self.ms.is_rebase_safe(b))

    def test_is_rebase_unsafe_public(self):
        b = BranchInfo(name="main", is_public=True)
        self.assertFalse(self.ms.is_rebase_safe(b))

    def test_is_rebase_unsafe_shared(self):
        b = BranchInfo(name="feat", has_shared_commits=True)
        self.assertFalse(self.ms.is_rebase_safe(b))

    def test_is_rebase_unsafe_multi_author(self):
        b = BranchInfo(name="feat", authors=["alice", "bob"])
        self.assertFalse(self.ms.is_rebase_safe(b))


if __name__ == "__main__":
    unittest.main()
