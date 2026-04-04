"""Tests for lidco.jira.sync."""
from __future__ import annotations

import unittest

from lidco.jira.client import JiraClient
from lidco.jira.sync import IssueSync, TodoItem, SyncRecord


class TestSyncRecord(unittest.TestCase):
    def test_defaults(self):
        r = SyncRecord(issue_key="X-1", direction="to_jira")
        self.assertEqual(r.status, "pending")
        self.assertGreater(r.timestamp, 0)

    def test_custom(self):
        r = SyncRecord(issue_key="X-1", direction="from_jira", status="synced", detail="ok")
        self.assertEqual(r.status, "synced")
        self.assertEqual(r.detail, "ok")


class TestTodoItem(unittest.TestCase):
    def test_defaults(self):
        t = TodoItem(title="Do thing")
        self.assertFalse(t.done)
        self.assertEqual(t.issue_key, "")
        self.assertEqual(t.tags, [])


class TestIssueSync(unittest.TestCase):
    def setUp(self):
        self.client = JiraClient()
        self.client.add_project("PROJ", "Project")
        self.sync = IssueSync(self.client, project="PROJ")

    def test_client_property(self):
        self.assertIs(self.sync.client, self.client)

    def test_sync_from_todo_create(self):
        todos = [TodoItem(title="New task"), TodoItem(title="Another")]
        issues = self.sync.sync_from_todo(todos)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0].summary, "New task")
        self.assertEqual(issues[0].project, "PROJ")

    def test_sync_from_todo_update(self):
        iss = self.client.create_issue("Old", project="PROJ")
        todos = [TodoItem(title="Updated", issue_key=iss.key, done=True)]
        issues = self.sync.sync_from_todo(todos)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].summary, "Updated")
        self.assertEqual(issues[0].status, "Done")

    def test_sync_from_todo_missing_key(self):
        todos = [TodoItem(title="Ghost", issue_key="NOPE-999")]
        issues = self.sync.sync_from_todo(todos)
        self.assertEqual(len(issues), 0)
        failed = self.sync.failed_syncs()
        self.assertEqual(len(failed), 1)

    def test_sync_from_jira(self):
        self.client.create_issue("Task A", project="PROJ")
        self.client.create_issue("Task B", project="PROJ")
        todos = self.sync.sync_from_jira()
        self.assertEqual(len(todos), 2)
        self.assertFalse(todos[0].done)
        self.assertTrue(todos[0].issue_key.startswith("PROJ-"))

    def test_sync_from_jira_with_jql(self):
        self.client.create_issue("Bug", issue_type="Bug", project="PROJ")
        self.client.create_issue("Task", issue_type="Task", project="PROJ")
        todos = self.sync.sync_from_jira(jql='type = Bug')
        self.assertEqual(len(todos), 1)

    def test_update_status(self):
        iss = self.client.create_issue("WIP", project="PROJ")
        updated = self.sync.update_status(iss.key, "In Progress")
        self.assertEqual(updated.status, "In Progress")

    def test_link_pr(self):
        iss = self.client.create_issue("PR me", project="PROJ")
        self.sync.link_pr(iss.key, "https://github.com/org/repo/pull/1")
        links = self.sync.get_pr_links(iss.key)
        self.assertEqual(len(links), 1)
        self.assertIn("pull/1", links[0])

    def test_link_pr_multiple(self):
        iss = self.client.create_issue("Multi PR", project="PROJ")
        self.sync.link_pr(iss.key, "https://github.com/a/pull/1")
        self.sync.link_pr(iss.key, "https://github.com/a/pull/2")
        self.assertEqual(len(self.sync.get_pr_links(iss.key)), 2)

    def test_link_pr_missing_issue(self):
        with self.assertRaises(KeyError):
            self.sync.link_pr("NOPE-1", "http://example.com")

    def test_pending_syncs(self):
        # All synced records have status="synced", so pending is empty
        self.sync.sync_from_todo([TodoItem(title="x")])
        self.assertEqual(len(self.sync.pending_syncs()), 0)

    def test_all_records(self):
        self.sync.sync_from_todo([TodoItem(title="a"), TodoItem(title="b")])
        self.assertEqual(len(self.sync.all_records()), 2)

    def test_get_pr_links_empty(self):
        self.assertEqual(self.sync.get_pr_links("NOPE-1"), [])
