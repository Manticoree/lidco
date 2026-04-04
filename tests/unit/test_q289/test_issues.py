"""Tests for lidco.github.issues — IssueManager."""
from __future__ import annotations

import unittest

from lidco.github.issues import IssueManager, Issue


class TestIssueManager(unittest.TestCase):
    def setUp(self):
        self.mgr = IssueManager()

    # -- create -----------------------------------------------------------

    def test_create_returns_issue(self):
        issue = self.mgr.create("Bug title", "description")
        self.assertIsInstance(issue, Issue)
        self.assertEqual(issue.title, "Bug title")
        self.assertEqual(issue.state, "open")

    def test_create_empty_title_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.create("")

    def test_create_increments_id(self):
        i1 = self.mgr.create("A")
        i2 = self.mgr.create("B")
        self.assertEqual(i2.id, i1.id + 1)

    # -- update -----------------------------------------------------------

    def test_update_changes_title(self):
        issue = self.mgr.create("Old")
        updated = self.mgr.update(issue.id, title="New")
        self.assertEqual(updated.title, "New")

    def test_update_missing_raises(self):
        with self.assertRaises(KeyError):
            self.mgr.update(999, title="x")

    # -- close ------------------------------------------------------------

    def test_close_success(self):
        issue = self.mgr.create("Bug")
        self.assertTrue(self.mgr.close(issue.id))
        self.assertEqual(issue.state, "closed")

    def test_close_missing_returns_false(self):
        self.assertFalse(self.mgr.close(999))

    # -- auto_label -------------------------------------------------------

    def test_auto_label_adds_labels(self):
        issue = self.mgr.create("Bug")
        labels = self.mgr.auto_label(issue.id, ["bug", "critical"])
        self.assertIn("bug", labels)
        self.assertIn("critical", labels)

    def test_auto_label_no_duplicates(self):
        issue = self.mgr.create("Bug")
        self.mgr.auto_label(issue.id, ["bug"])
        labels = self.mgr.auto_label(issue.id, ["bug", "new"])
        self.assertEqual(labels.count("bug"), 1)

    def test_auto_label_missing_raises(self):
        with self.assertRaises(KeyError):
            self.mgr.auto_label(999, ["bug"])

    # -- link_to_pr -------------------------------------------------------

    def test_link_to_pr_success(self):
        issue = self.mgr.create("A")
        self.assertTrue(self.mgr.link_to_pr(issue.id, 42))
        self.assertIn(42, issue.linked_prs)

    def test_link_to_pr_no_dup(self):
        issue = self.mgr.create("A")
        self.mgr.link_to_pr(issue.id, 42)
        self.mgr.link_to_pr(issue.id, 42)
        self.assertEqual(issue.linked_prs.count(42), 1)

    def test_link_to_pr_missing_returns_false(self):
        self.assertFalse(self.mgr.link_to_pr(999, 1))

    # -- list_issues ------------------------------------------------------

    def test_list_issues_all(self):
        self.mgr.create("A")
        self.mgr.create("B")
        self.assertEqual(len(self.mgr.list_issues()), 2)

    def test_list_issues_filter_state(self):
        i1 = self.mgr.create("A")
        self.mgr.create("B")
        self.mgr.close(i1.id)
        open_issues = self.mgr.list_issues({"state": "open"})
        self.assertEqual(len(open_issues), 1)

    def test_list_issues_filter_label(self):
        i1 = self.mgr.create("A")
        self.mgr.create("B")
        self.mgr.auto_label(i1.id, ["bug"])
        bugs = self.mgr.list_issues({"label": "bug"})
        self.assertEqual(len(bugs), 1)


if __name__ == "__main__":
    unittest.main()
