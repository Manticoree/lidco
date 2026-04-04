"""Tests for lidco.jira.client."""
from __future__ import annotations

import unittest

from lidco.jira.client import JiraClient, Issue, Project


class TestIssue(unittest.TestCase):
    def test_defaults(self):
        iss = Issue(key="X-1", summary="test")
        self.assertEqual(iss.key, "X-1")
        self.assertEqual(iss.summary, "test")
        self.assertEqual(iss.issue_type, "Task")
        self.assertEqual(iss.status, "To Do")
        self.assertEqual(iss.priority, "Medium")
        self.assertIsInstance(iss.labels, list)
        self.assertGreater(iss.created_at, 0)

    def test_custom_fields(self):
        iss = Issue(key="A-1", summary="s", issue_type="Bug", status="Done", priority="High")
        self.assertEqual(iss.issue_type, "Bug")
        self.assertEqual(iss.status, "Done")
        self.assertEqual(iss.priority, "High")


class TestProject(unittest.TestCase):
    def test_defaults(self):
        p = Project(key="PROJ", name="My Project")
        self.assertEqual(p.key, "PROJ")
        self.assertEqual(p.lead, "")
        self.assertEqual(p.issue_count, 0)


class TestJiraClient(unittest.TestCase):
    def setUp(self):
        self.client = JiraClient(base_url="https://test.jira.com", token="tok")

    def test_base_url(self):
        self.assertEqual(self.client.base_url, "https://test.jira.com")

    def test_add_project(self):
        p = self.client.add_project("DEV", "Development", lead="alice")
        self.assertEqual(p.key, "DEV")
        self.assertEqual(p.name, "Development")
        self.assertEqual(p.lead, "alice")

    def test_list_projects(self):
        self.assertEqual(len(self.client.list_projects()), 0)
        self.client.add_project("A", "Alpha")
        self.client.add_project("B", "Beta")
        self.assertEqual(len(self.client.list_projects()), 2)

    def test_create_issue(self):
        self.client.add_project("PROJ", "Project")
        iss = self.client.create_issue("Fix bug", issue_type="Bug", project="PROJ")
        self.assertEqual(iss.key, "PROJ-1")
        self.assertEqual(iss.summary, "Fix bug")
        self.assertEqual(iss.issue_type, "Bug")

    def test_create_issue_auto_project(self):
        iss = self.client.create_issue("Task 1", project="NEW")
        self.assertEqual(iss.project, "NEW")
        self.assertIn("NEW", [p.key for p in self.client.list_projects()])

    def test_create_issue_sequential_keys(self):
        self.client.add_project("P", "P")
        i1 = self.client.create_issue("a", project="P")
        i2 = self.client.create_issue("b", project="P")
        self.assertEqual(i1.key, "P-1")
        self.assertEqual(i2.key, "P-2")

    def test_get_issue(self):
        self.client.add_project("X", "X")
        created = self.client.create_issue("Test", project="X")
        fetched = self.client.get_issue(created.key)
        self.assertEqual(fetched.summary, "Test")

    def test_get_issue_not_found(self):
        with self.assertRaises(KeyError):
            self.client.get_issue("NOPE-1")

    def test_update_issue(self):
        self.client.add_project("U", "U")
        iss = self.client.create_issue("Old", project="U")
        updated = self.client.update_issue(iss.key, summary="New", status="In Progress")
        self.assertEqual(updated.summary, "New")
        self.assertEqual(updated.status, "In Progress")
        self.assertEqual(updated.project, "U")

    def test_delete_issue(self):
        self.client.add_project("D", "D")
        iss = self.client.create_issue("Gone", project="D")
        self.client.delete_issue(iss.key)
        with self.assertRaises(KeyError):
            self.client.get_issue(iss.key)

    def test_delete_issue_not_found(self):
        with self.assertRaises(KeyError):
            self.client.delete_issue("NOPE-1")

    def test_search_jql_project(self):
        self.client.add_project("A", "A")
        self.client.add_project("B", "B")
        self.client.create_issue("i1", project="A")
        self.client.create_issue("i2", project="B")
        results = self.client.search_jql('project = A')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].project, "A")

    def test_search_jql_status(self):
        self.client.add_project("S", "S")
        iss = self.client.create_issue("i1", project="S")
        self.client.update_issue(iss.key, status="Done")
        results = self.client.search_jql('status = Done')
        self.assertEqual(len(results), 1)

    def test_search_jql_text(self):
        self.client.add_project("T", "T")
        self.client.create_issue("Fix login bug", project="T")
        self.client.create_issue("Add feature", project="T")
        results = self.client.search_jql('text ~ login')
        self.assertEqual(len(results), 1)
        self.assertIn("login", results[0].summary.lower())

    def test_search_jql_pagination(self):
        self.client.add_project("P", "P")
        for i in range(5):
            self.client.create_issue(f"item {i}", project="P")
        page1 = self.client.search_jql('project = P', max_results=2, start_at=0)
        page2 = self.client.search_jql('project = P', max_results=2, start_at=2)
        self.assertEqual(len(page1), 2)
        self.assertEqual(len(page2), 2)
        self.assertNotEqual(page1[0].key, page2[0].key)

    def test_search_jql_and(self):
        self.client.add_project("M", "M")
        i1 = self.client.create_issue("Bug fix", issue_type="Bug", project="M")
        i2 = self.client.create_issue("Task work", issue_type="Task", project="M")
        results = self.client.search_jql('project = M AND type = Bug')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].issue_type, "Bug")

    def test_all_issues(self):
        self.client.add_project("Z", "Z")
        self.client.create_issue("a", project="Z")
        self.client.create_issue("b", project="Z")
        self.assertEqual(len(self.client.all_issues()), 2)
