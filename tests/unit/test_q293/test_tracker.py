"""Tests for lidco.linear.tracker."""
from __future__ import annotations

import unittest

from lidco.linear.client import LinearClient
from lidco.linear.tracker import IssueTracker


class TestIssueTracker(unittest.TestCase):
    def setUp(self):
        self.client = LinearClient()
        self.tracker = IssueTracker(self.client)

    def test_create_from_code(self):
        issue = self.tracker.create_from_code("Bug in parser", "src/parser.py")
        self.assertIn("parser.py", issue.description)
        self.assertEqual(issue.title, "Bug in parser")

    def test_create_from_code_custom_team(self):
        issue = self.tracker.create_from_code("T", "f.py", team="Design")
        self.assertEqual(issue.team, "Design")

    def test_link_pr(self):
        issue = self.client.create_issue("Fix", "Eng")
        self.tracker.link_pr(issue.id, "https://github.com/org/repo/pull/1")
        links = self.tracker.get_pr_links(issue.id)
        self.assertEqual(len(links), 1)
        self.assertIn("pull/1", links[0])

    def test_link_pr_duplicate_ignored(self):
        issue = self.client.create_issue("Fix", "Eng")
        url = "https://github.com/org/repo/pull/2"
        self.tracker.link_pr(issue.id, url)
        self.tracker.link_pr(issue.id, url)
        self.assertEqual(len(self.tracker.get_pr_links(issue.id)), 1)

    def test_link_pr_nonexistent_issue(self):
        with self.assertRaises(KeyError):
            self.tracker.link_pr("nonexistent", "http://example.com")

    def test_update_status(self):
        issue = self.client.create_issue("X", "T")
        updated = self.tracker.update_status(issue.id, "In Progress")
        self.assertEqual(updated.status, "In Progress")

    def test_update_status_invalid(self):
        issue = self.client.create_issue("X", "T")
        with self.assertRaises(ValueError):
            self.tracker.update_status(issue.id, "InvalidStatus")

    def test_auto_status_feature(self):
        self.assertEqual(self.tracker.auto_status("feature/login"), "In Progress")

    def test_auto_status_feat(self):
        self.assertEqual(self.tracker.auto_status("feat/add-button"), "In Progress")

    def test_auto_status_fix(self):
        self.assertEqual(self.tracker.auto_status("fix/null-pointer"), "In Progress")

    def test_auto_status_bugfix(self):
        self.assertEqual(self.tracker.auto_status("bugfix/crash"), "In Progress")

    def test_auto_status_review(self):
        self.assertEqual(self.tracker.auto_status("review/42"), "In Review")

    def test_auto_status_pr(self):
        self.assertEqual(self.tracker.auto_status("pr/123"), "In Review")

    def test_auto_status_main(self):
        self.assertEqual(self.tracker.auto_status("main"), "Done")

    def test_auto_status_master(self):
        self.assertEqual(self.tracker.auto_status("master"), "Done")

    def test_auto_status_release(self):
        self.assertEqual(self.tracker.auto_status("release/v2.0"), "Done")

    def test_auto_status_unknown(self):
        self.assertEqual(self.tracker.auto_status("random-branch"), "Todo")

    def test_get_pr_links_empty(self):
        self.assertEqual(self.tracker.get_pr_links("nonexistent"), [])

    def test_client_property(self):
        self.assertIs(self.tracker.client, self.client)


if __name__ == "__main__":
    unittest.main()
