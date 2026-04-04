"""Tests for lidco.linear.client."""
from __future__ import annotations

import unittest

from lidco.linear.client import Issue, LinearClient, Team


class TestIssueDataclass(unittest.TestCase):
    def test_defaults(self):
        i = Issue(id="LIN-1", title="Bug", team="Eng")
        self.assertEqual(i.id, "LIN-1")
        self.assertEqual(i.status, "Todo")
        self.assertEqual(i.labels, [])
        self.assertIsNone(i.assignee)
        self.assertGreater(i.created_at, 0)

    def test_custom_fields(self):
        i = Issue(id="X", title="T", team="T", status="Done", priority=3, labels=["a"])
        self.assertEqual(i.status, "Done")
        self.assertEqual(i.priority, 3)
        self.assertEqual(i.labels, ["a"])


class TestTeamDataclass(unittest.TestCase):
    def test_team(self):
        t = Team(id="t1", name="Eng", key="ENG")
        self.assertEqual(t.key, "ENG")


class TestLinearClient(unittest.TestCase):
    def setUp(self):
        self.client = LinearClient(api_key="test-key")

    def test_list_teams(self):
        teams = self.client.list_teams()
        self.assertGreaterEqual(len(teams), 3)
        keys = [t.key for t in teams]
        self.assertIn("ENG", keys)

    def test_create_issue(self):
        issue = self.client.create_issue("Fix bug", "Engineering")
        self.assertTrue(issue.id.startswith("LIN-"))
        self.assertEqual(issue.title, "Fix bug")
        self.assertEqual(issue.team, "Engineering")
        self.assertEqual(issue.status, "Todo")

    def test_create_issue_empty_title_raises(self):
        with self.assertRaises(ValueError):
            self.client.create_issue("", "Engineering")

    def test_create_issue_empty_team_raises(self):
        with self.assertRaises(ValueError):
            self.client.create_issue("Bug", "")

    def test_get_issue(self):
        created = self.client.create_issue("Test", "Eng")
        fetched = self.client.get_issue(created.id)
        self.assertEqual(fetched.title, "Test")

    def test_get_issue_not_found(self):
        with self.assertRaises(KeyError):
            self.client.get_issue("nonexistent")

    def test_list_issues(self):
        self.client.create_issue("A", "TeamA")
        self.client.create_issue("B", "TeamA")
        self.client.create_issue("C", "TeamB")
        issues = self.client.list_issues("TeamA")
        self.assertEqual(len(issues), 2)

    def test_list_issues_filter_status(self):
        i = self.client.create_issue("A", "T1")
        self.client.update_issue(i.id, status="Done")
        self.client.create_issue("B", "T1")
        done = self.client.list_issues("T1", status="Done")
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0].status, "Done")

    def test_update_issue(self):
        issue = self.client.create_issue("X", "T")
        updated = self.client.update_issue(issue.id, status="In Progress", priority=5)
        self.assertEqual(updated.status, "In Progress")
        self.assertEqual(updated.priority, 5)

    def test_update_issue_invalid_field(self):
        issue = self.client.create_issue("X", "T")
        with self.assertRaises(ValueError):
            self.client.update_issue(issue.id, bad_field="oops")

    def test_create_issue_with_labels_and_assignee(self):
        issue = self.client.create_issue(
            "Feat", "Eng", labels=["feat", "urgent"], assignee="alice"
        )
        self.assertEqual(issue.labels, ["feat", "urgent"])
        self.assertEqual(issue.assignee, "alice")


if __name__ == "__main__":
    unittest.main()
