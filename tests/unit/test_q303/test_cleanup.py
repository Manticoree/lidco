"""Tests for lidco.branches.cleanup."""
from __future__ import annotations

import time
import unittest

from lidco.branches.cleanup import BranchCleanup


class TestAddBranch(unittest.TestCase):
    def test_add_single(self):
        c = BranchCleanup()
        c.add_branch("feature/x", time.time(), merged=False)
        self.assertEqual(len(c._branches), 1)

    def test_add_overwrite(self):
        c = BranchCleanup()
        c.add_branch("feature/x", 100.0)
        c.add_branch("feature/x", 200.0)
        self.assertEqual(c._branches["feature/x"].last_activity, 200.0)


class TestStale(unittest.TestCase):
    def setUp(self):
        self.c = BranchCleanup()
        old = time.time() - 60 * 86400  # 60 days ago
        self.c.add_branch("feature/old", old)
        self.c.add_branch("feature/new", time.time())

    def test_stale_default_30(self):
        stale = self.c.stale(30)
        self.assertIn("feature/old", stale)
        self.assertNotIn("feature/new", stale)

    def test_stale_excludes_protected(self):
        self.c.protected(["feature/old"])
        stale = self.c.stale(30)
        self.assertNotIn("feature/old", stale)

    def test_stale_custom_days(self):
        stale = self.c.stale(90)
        self.assertNotIn("feature/old", stale)

    def test_stale_zero_days(self):
        # everything except protected is stale with 0 days
        stale = self.c.stale(0)
        self.assertIn("feature/old", stale)
        self.assertIn("feature/new", stale)


class TestMerged(unittest.TestCase):
    def test_merged_returns_merged_only(self):
        c = BranchCleanup()
        c.add_branch("feature/a", time.time(), merged=True)
        c.add_branch("feature/b", time.time(), merged=False)
        self.assertEqual(c.merged(), ["feature/a"])

    def test_merged_excludes_protected(self):
        c = BranchCleanup()
        c.add_branch("main", time.time(), merged=True)
        self.assertEqual(c.merged(), [])


class TestOrphaned(unittest.TestCase):
    def test_orphaned(self):
        c = BranchCleanup()
        very_old = time.time() - 100 * 86400
        c.add_branch("feature/orphan", very_old, merged=False)
        c.add_branch("feature/merged-old", very_old, merged=True)
        c.add_branch("feature/recent", time.time(), merged=False)
        orphaned = c.orphaned()
        self.assertIn("feature/orphan", orphaned)
        self.assertNotIn("feature/merged-old", orphaned)
        self.assertNotIn("feature/recent", orphaned)

    def test_orphaned_excludes_protected(self):
        c = BranchCleanup()
        very_old = time.time() - 100 * 86400
        c.add_branch("main", very_old, merged=False)
        self.assertEqual(c.orphaned(), [])


class TestBulkDelete(unittest.TestCase):
    def test_delete_existing(self):
        c = BranchCleanup()
        c.add_branch("feature/a", time.time())
        c.add_branch("feature/b", time.time())
        count = c.bulk_delete(["feature/a", "feature/b"])
        self.assertEqual(count, 2)
        self.assertEqual(len(c._branches), 0)

    def test_delete_skips_protected(self):
        c = BranchCleanup()
        c.add_branch("main", time.time())
        count = c.bulk_delete(["main"])
        self.assertEqual(count, 0)
        self.assertIn("main", c._branches)

    def test_delete_nonexistent(self):
        c = BranchCleanup()
        count = c.bulk_delete(["nonexistent"])
        self.assertEqual(count, 0)


class TestProtected(unittest.TestCase):
    def test_protect_adds(self):
        c = BranchCleanup()
        c.protected(["release", "develop"])
        self.assertIn("release", c._protected)
        self.assertIn("develop", c._protected)

    def test_protect_defaults(self):
        c = BranchCleanup()
        self.assertIn("main", c._protected)
        self.assertIn("master", c._protected)


if __name__ == "__main__":
    unittest.main()
