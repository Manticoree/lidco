"""Tests for lidco.branches.worktree_v2."""
from __future__ import annotations

import time
import unittest

from lidco.branches.worktree_v2 import Worktree, WorktreeManagerV2


class TestWorktreeDataclass(unittest.TestCase):
    def test_defaults(self):
        wt = Worktree(branch="main", path="/tmp/wt")
        self.assertEqual(wt.branch, "main")
        self.assertEqual(wt.path, "/tmp/wt")
        self.assertGreater(wt.created_at, 0)

    def test_explicit_created_at(self):
        wt = Worktree(branch="dev", path="/p", created_at=42.0)
        self.assertEqual(wt.created_at, 42.0)


class TestCreate(unittest.TestCase):
    def setUp(self):
        self.mgr = WorktreeManagerV2()

    def test_create_returns_worktree(self):
        wt = self.mgr.create("feature/x", "/tmp/wt1")
        self.assertIsInstance(wt, Worktree)
        self.assertEqual(wt.branch, "feature/x")
        self.assertEqual(wt.path, "/tmp/wt1")

    def test_create_auto_path(self):
        wt = self.mgr.create("feature/x")
        self.assertIn("feature_x", wt.path)

    def test_create_duplicate_raises(self):
        self.mgr.create("a", "/tmp/wt1")
        with self.assertRaises(ValueError):
            self.mgr.create("b", "/tmp/wt1")

    def test_create_multiple(self):
        self.mgr.create("a", "/tmp/a")
        self.mgr.create("b", "/tmp/b")
        self.assertEqual(len(self.mgr.list_worktrees()), 2)


class TestRemove(unittest.TestCase):
    def setUp(self):
        self.mgr = WorktreeManagerV2()

    def test_remove_existing(self):
        self.mgr.create("a", "/tmp/a")
        self.assertTrue(self.mgr.remove("/tmp/a"))

    def test_remove_nonexistent(self):
        self.assertFalse(self.mgr.remove("/tmp/nope"))

    def test_remove_clears_list(self):
        self.mgr.create("a", "/tmp/a")
        self.mgr.remove("/tmp/a")
        self.assertEqual(len(self.mgr.list_worktrees()), 0)


class TestListWorktrees(unittest.TestCase):
    def test_empty(self):
        mgr = WorktreeManagerV2()
        self.assertEqual(mgr.list_worktrees(), [])

    def test_returns_all(self):
        mgr = WorktreeManagerV2()
        mgr.create("a", "/tmp/a")
        mgr.create("b", "/tmp/b")
        names = [w.branch for w in mgr.list_worktrees()]
        self.assertIn("a", names)
        self.assertIn("b", names)


class TestAutoCleanup(unittest.TestCase):
    def test_cleanup_old(self):
        mgr = WorktreeManagerV2()
        wt = mgr.create("old", "/tmp/old")
        # Manually backdate
        wt.created_at = time.time() - 100000
        count = mgr.auto_cleanup(max_age_seconds=1000)
        self.assertEqual(count, 1)
        self.assertEqual(len(mgr.list_worktrees()), 0)

    def test_cleanup_keeps_recent(self):
        mgr = WorktreeManagerV2()
        mgr.create("new", "/tmp/new")
        count = mgr.auto_cleanup(max_age_seconds=86400)
        self.assertEqual(count, 0)
        self.assertEqual(len(mgr.list_worktrees()), 1)

    def test_cleanup_mixed(self):
        mgr = WorktreeManagerV2()
        old = mgr.create("old", "/tmp/old")
        old.created_at = time.time() - 200000
        mgr.create("new", "/tmp/new")
        count = mgr.auto_cleanup(max_age_seconds=1000)
        self.assertEqual(count, 1)
        self.assertEqual(len(mgr.list_worktrees()), 1)


class TestDiskUsage(unittest.TestCase):
    def test_empty(self):
        mgr = WorktreeManagerV2()
        self.assertEqual(mgr.disk_usage(), {})

    def test_nonexistent_path_returns_zero(self):
        mgr = WorktreeManagerV2()
        mgr.create("a", "/tmp/nonexistent_lidco_worktree_12345")
        usage = mgr.disk_usage()
        self.assertEqual(usage["/tmp/nonexistent_lidco_worktree_12345"], 0)


class TestSharedCachePath(unittest.TestCase):
    def test_default(self):
        mgr = WorktreeManagerV2()
        self.assertEqual(mgr.shared_cache_path(), ".worktrees/.cache")

    def test_custom(self):
        mgr = WorktreeManagerV2(_cache_path="/custom/cache")
        self.assertEqual(mgr.shared_cache_path(), "/custom/cache")


if __name__ == "__main__":
    unittest.main()
