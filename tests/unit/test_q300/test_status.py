"""Tests for PRStatusTracker (Q300)."""
import unittest

from lidco.pr.status import PRStatusTracker, PRStatus, CIStatus, ReviewState


class TestPRStatusTracker(unittest.TestCase):

    def test_track_creates_new(self):
        t = PRStatusTracker()
        pr = t.track("PR-1")
        self.assertEqual(pr.pr_id, "PR-1")
        self.assertEqual(pr.ci_status, CIStatus.PENDING)

    def test_track_returns_existing(self):
        t = PRStatusTracker()
        pr1 = t.track("PR-1")
        pr2 = t.track("PR-1")
        self.assertEqual(pr1.pr_id, pr2.pr_id)

    def test_update_ci_passed(self):
        t = PRStatusTracker()
        pr = t.update_ci("PR-1", "passed")
        self.assertEqual(pr.ci_status, CIStatus.PASSED)
        self.assertTrue(pr.ci_passed)

    def test_update_ci_failed(self):
        t = PRStatusTracker()
        pr = t.update_ci("PR-1", "failed")
        self.assertEqual(pr.ci_status, CIStatus.FAILED)
        self.assertFalse(pr.ci_passed)

    def test_update_ci_invalid(self):
        t = PRStatusTracker()
        with self.assertRaises(ValueError):
            t.update_ci("PR-1", "invalid-status")

    def test_update_review_approve(self):
        t = PRStatusTracker()
        pr = t.update_review("PR-1", "alice", True)
        self.assertEqual(pr.approval_count, 1)
        self.assertTrue(pr.is_approved)

    def test_update_review_reject(self):
        t = PRStatusTracker()
        pr = t.update_review("PR-1", "bob", False)
        self.assertEqual(pr.approval_count, 0)
        self.assertFalse(pr.is_approved)

    def test_is_ready_requires_ci_and_approval(self):
        t = PRStatusTracker()
        t.update_ci("PR-1", "passed")
        self.assertFalse(t.is_ready("PR-1"))
        t.update_review("PR-1", "alice", True)
        self.assertTrue(t.is_ready("PR-1"))

    def test_is_ready_false_without_ci(self):
        t = PRStatusTracker()
        t.update_review("PR-1", "alice", True)
        self.assertFalse(t.is_ready("PR-1"))

    def test_auto_merge_eligible(self):
        t = PRStatusTracker()
        t.update_ci("PR-1", "passed")
        t.update_review("PR-1", "alice", True)
        self.assertTrue(t.auto_merge_eligible("PR-1"))

    def test_auto_merge_not_eligible_with_rejection(self):
        t = PRStatusTracker()
        t.update_ci("PR-1", "passed")
        t.update_review("PR-1", "alice", True)
        t.update_review("PR-1", "bob", False)
        self.assertFalse(t.auto_merge_eligible("PR-1"))

    def test_auto_merge_not_eligible_without_ready(self):
        t = PRStatusTracker()
        self.assertFalse(t.auto_merge_eligible("PR-1"))

    def test_get_returns_none_for_untracked(self):
        t = PRStatusTracker()
        self.assertIsNone(t.get("PR-999"))

    def test_get_returns_status(self):
        t = PRStatusTracker()
        t.track("PR-1")
        self.assertIsNotNone(t.get("PR-1"))

    def test_list_tracked(self):
        t = PRStatusTracker()
        t.track("PR-1")
        t.track("PR-2")
        self.assertEqual(sorted(t.list_tracked()), ["PR-1", "PR-2"])

    def test_required_approvals(self):
        t = PRStatusTracker(required_approvals=2)
        t.update_ci("PR-1", "passed")
        t.update_review("PR-1", "alice", True)
        self.assertFalse(t.is_ready("PR-1"))
        t.update_review("PR-1", "bob", True)
        self.assertTrue(t.is_ready("PR-1"))

    def test_review_state_dataclass(self):
        rs = ReviewState(reviewer="x", approved=True, reviewed_at=100.0)
        self.assertEqual(rs.reviewer, "x")
        self.assertTrue(rs.approved)

    def test_ci_status_enum_values(self):
        self.assertEqual(CIStatus.PENDING.value, "pending")
        self.assertEqual(CIStatus.RUNNING.value, "running")
        self.assertEqual(CIStatus.PASSED.value, "passed")
        self.assertEqual(CIStatus.FAILED.value, "failed")


if __name__ == "__main__":
    unittest.main()
