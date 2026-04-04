"""Tests for lidco.github.pr_workflow — PRWorkflow."""
from __future__ import annotations

import unittest

from lidco.github.pr_workflow import PRWorkflow, PR


class TestPRWorkflow(unittest.TestCase):
    def setUp(self):
        self.wf = PRWorkflow()

    # -- create_pr --------------------------------------------------------

    def test_create_pr_returns_pr(self):
        pr = self.wf.create_pr("Fix bug", "Fixes #1", "fix-bug")
        self.assertIsInstance(pr, PR)
        self.assertEqual(pr.title, "Fix bug")
        self.assertEqual(pr.branch, "fix-bug")
        self.assertEqual(pr.base, "main")
        self.assertEqual(pr.state, "open")

    def test_create_pr_increments_id(self):
        pr1 = self.wf.create_pr("A", "", "a")
        pr2 = self.wf.create_pr("B", "", "b")
        self.assertEqual(pr2.id, pr1.id + 1)

    def test_create_pr_empty_title_raises(self):
        with self.assertRaises(ValueError):
            self.wf.create_pr("", "body", "branch")

    def test_create_pr_empty_branch_raises(self):
        with self.assertRaises(ValueError):
            self.wf.create_pr("title", "body", "")

    def test_create_pr_custom_base(self):
        pr = self.wf.create_pr("X", "", "feat", base="develop")
        self.assertEqual(pr.base, "develop")

    # -- auto_describe ----------------------------------------------------

    def test_auto_describe_empty_diff(self):
        desc = self.wf.auto_describe("")
        self.assertIn("No changes", desc)

    def test_auto_describe_counts_additions_deletions(self):
        diff = "+added line\n-removed line\n context"
        desc = self.wf.auto_describe(diff)
        self.assertIn("1 addition", desc)
        self.assertIn("1 deletion", desc)

    def test_auto_describe_ignores_diff_headers(self):
        diff = "--- a/file.py\n+++ b/file.py\n+new line"
        desc = self.wf.auto_describe(diff)
        self.assertIn("1 addition", desc)

    # -- request_reviewers ------------------------------------------------

    def test_request_reviewers_success(self):
        pr = self.wf.create_pr("T", "", "b")
        ok = self.wf.request_reviewers(pr.id, ["alice", "bob"])
        self.assertTrue(ok)
        self.assertIn("alice", pr.reviewers)

    def test_request_reviewers_missing_pr(self):
        self.assertFalse(self.wf.request_reviewers(999, ["alice"]))

    # -- list_reviews -----------------------------------------------------

    def test_list_reviews_empty_for_new_pr(self):
        pr = self.wf.create_pr("T", "", "b")
        self.assertEqual(self.wf.list_reviews(pr.id), [])

    def test_list_reviews_after_request(self):
        pr = self.wf.create_pr("T", "", "b")
        self.wf.request_reviewers(pr.id, ["alice"])
        reviews = self.wf.list_reviews(pr.id)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["reviewer"], "alice")

    def test_list_reviews_missing_pr(self):
        self.assertEqual(self.wf.list_reviews(999), [])


if __name__ == "__main__":
    unittest.main()
