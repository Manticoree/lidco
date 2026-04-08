"""Tests for snapshot_test.reviewer — SnapshotReviewer."""

import tempfile
import unittest

from lidco.snapshot_test.manager import SnapshotManager
from lidco.snapshot_test.reviewer import SnapshotReviewer, ReviewItem, ReviewDecision


class TestReviewerBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.mgr = SnapshotManager(self._td.name)
        self.reviewer = SnapshotReviewer(self.mgr)

    def tearDown(self):
        self._td.cleanup()


class TestAddPending(TestReviewerBase):
    def test_add_returns_review_item(self):
        self.mgr.create("snap1", "old")
        item = self.reviewer.add_pending("snap1", "new")
        self.assertIsInstance(item, ReviewItem)
        self.assertEqual(item.name, "snap1")

    def test_add_sets_old_content(self):
        self.mgr.create("snap1", "old")
        item = self.reviewer.add_pending("snap1", "new")
        self.assertEqual(item.old_content, "old")

    def test_add_sets_new_content(self):
        self.mgr.create("snap1", "old")
        item = self.reviewer.add_pending("snap1", "new")
        self.assertEqual(item.new_content, "new")

    def test_add_generates_diff(self):
        self.mgr.create("snap1", "old")
        item = self.reviewer.add_pending("snap1", "new")
        self.assertIn("-old", item.diff)

    def test_add_nonexistent_snapshot(self):
        item = self.reviewer.add_pending("nosuch", "val")
        self.assertEqual(item.old_content, "")

    def test_pending_count(self):
        self.reviewer.add_pending("a", "1")
        self.reviewer.add_pending("b", "2")
        self.assertEqual(self.reviewer.pending_count(), 2)


class TestListPending(TestReviewerBase):
    def test_empty(self):
        self.assertEqual(self.reviewer.list_pending(), [])

    def test_sorted_by_name(self):
        self.reviewer.add_pending("beta", "1")
        self.reviewer.add_pending("alpha", "2")
        names = [p.name for p in self.reviewer.list_pending()]
        self.assertEqual(names, ["alpha", "beta"])


class TestAcceptReject(TestReviewerBase):
    def test_accept_updates_snapshot(self):
        self.mgr.create("snap1", "old")
        self.reviewer.add_pending("snap1", "new")
        d = self.reviewer.accept("snap1")
        self.assertIsNotNone(d)
        self.assertTrue(d.accepted)
        rec = self.mgr.read("snap1")
        self.assertEqual(rec.content, "new")

    def test_accept_removes_from_pending(self):
        self.reviewer.add_pending("snap1", "new")
        self.reviewer.accept("snap1")
        self.assertEqual(self.reviewer.pending_count(), 0)

    def test_reject_leaves_snapshot(self):
        self.mgr.create("snap1", "old")
        self.reviewer.add_pending("snap1", "new")
        d = self.reviewer.reject("snap1")
        self.assertIsNotNone(d)
        self.assertFalse(d.accepted)
        rec = self.mgr.read("snap1")
        self.assertEqual(rec.content, "old")

    def test_accept_nonexistent_returns_none(self):
        self.assertIsNone(self.reviewer.accept("nope"))

    def test_reject_nonexistent_returns_none(self):
        self.assertIsNone(self.reviewer.reject("nope"))

    def test_accept_with_reviewer_name(self):
        self.reviewer.add_pending("snap1", "v")
        d = self.reviewer.accept("snap1", reviewer="alice")
        self.assertEqual(d.reviewer, "alice")


class TestBulkOps(TestReviewerBase):
    def test_accept_all(self):
        self.reviewer.add_pending("a", "1")
        self.reviewer.add_pending("b", "2")
        decisions = self.reviewer.accept_all()
        self.assertEqual(len(decisions), 2)
        self.assertEqual(self.reviewer.pending_count(), 0)

    def test_reject_all(self):
        self.reviewer.add_pending("a", "1")
        self.reviewer.add_pending("b", "2")
        decisions = self.reviewer.reject_all()
        self.assertEqual(len(decisions), 2)
        self.assertTrue(all(not d.accepted for d in decisions))

    def test_accept_all_empty(self):
        self.assertEqual(self.reviewer.accept_all(), [])


class TestHistory(TestReviewerBase):
    def test_history_empty(self):
        self.assertEqual(self.reviewer.get_history(), [])

    def test_history_after_accept(self):
        self.reviewer.add_pending("snap1", "v")
        self.reviewer.accept("snap1")
        hist = self.reviewer.get_history()
        self.assertEqual(len(hist), 1)
        self.assertTrue(hist[0].accepted)

    def test_history_filter_by_name(self):
        self.reviewer.add_pending("a", "1")
        self.reviewer.add_pending("b", "2")
        self.reviewer.accept("a")
        self.reviewer.reject("b")
        hist = self.reviewer.get_history(name="a")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0].name, "a")

    def test_clear_history(self):
        self.reviewer.add_pending("a", "1")
        self.reviewer.accept("a")
        count = self.reviewer.clear_history()
        self.assertEqual(count, 1)
        self.assertEqual(self.reviewer.get_history(), [])

    def test_history_persists(self):
        self.reviewer.add_pending("snap1", "v")
        self.reviewer.accept("snap1")
        # new instance loads history
        r2 = SnapshotReviewer(self.mgr)
        hist = r2.get_history()
        self.assertEqual(len(hist), 1)


if __name__ == "__main__":
    unittest.main()
