"""Tests for lidco.jira.sprint."""
from __future__ import annotations

import unittest

from lidco.jira.client import JiraClient
from lidco.jira.sprint import SprintPlanner, Sprint


class TestSprint(unittest.TestCase):
    def test_defaults(self):
        s = Sprint(id="s-1", name="Sprint 1")
        self.assertEqual(s.status, "future")
        self.assertEqual(s.issue_keys, [])
        self.assertEqual(s.estimates, {})
        self.assertEqual(s.capacity_points, 0)
        self.assertGreater(s.created_at, 0)

    def test_custom(self):
        s = Sprint(id="s-1", name="S", goal="Ship it", capacity_points=20)
        self.assertEqual(s.goal, "Ship it")
        self.assertEqual(s.capacity_points, 20)


class TestSprintPlanner(unittest.TestCase):
    def setUp(self):
        self.client = JiraClient()
        self.client.add_project("P", "Project")
        self.planner = SprintPlanner(self.client)

    def test_client_property(self):
        self.assertIs(self.planner.client, self.client)

    def test_create_sprint(self):
        s = self.planner.create_sprint("Sprint 1", goal="Go fast", capacity_points=30)
        self.assertEqual(s.name, "Sprint 1")
        self.assertEqual(s.goal, "Go fast")
        self.assertEqual(s.capacity_points, 30)
        self.assertEqual(s.status, "future")
        self.assertTrue(s.id.startswith("sprint-"))

    def test_get_sprint(self):
        s = self.planner.create_sprint("S")
        fetched = self.planner.get_sprint(s.id)
        self.assertEqual(fetched.name, "S")

    def test_get_sprint_not_found(self):
        with self.assertRaises(KeyError):
            self.planner.get_sprint("nope")

    def test_start_sprint(self):
        s = self.planner.create_sprint("S")
        started = self.planner.start_sprint(s.id)
        self.assertEqual(started.status, "active")
        self.assertGreater(started.started_at, 0)

    def test_close_sprint(self):
        s = self.planner.create_sprint("S")
        self.planner.start_sprint(s.id)
        closed = self.planner.close_sprint(s.id)
        self.assertEqual(closed.status, "closed")
        self.assertGreater(closed.ended_at, 0)

    def test_add_issue(self):
        s = self.planner.create_sprint("S")
        iss = self.client.create_issue("Task", project="P")
        updated = self.planner.add_issue(s.id, iss.key)
        self.assertIn(iss.key, updated.issue_keys)

    def test_add_issue_duplicate(self):
        s = self.planner.create_sprint("S")
        iss = self.client.create_issue("Task", project="P")
        self.planner.add_issue(s.id, iss.key)
        updated = self.planner.add_issue(s.id, iss.key)
        self.assertEqual(updated.issue_keys.count(iss.key), 1)

    def test_add_issue_missing(self):
        s = self.planner.create_sprint("S")
        with self.assertRaises(KeyError):
            self.planner.add_issue(s.id, "NOPE-1")

    def test_remove_issue(self):
        s = self.planner.create_sprint("S")
        iss = self.client.create_issue("Task", project="P")
        self.planner.add_issue(s.id, iss.key)
        updated = self.planner.remove_issue(s.id, iss.key)
        self.assertNotIn(iss.key, updated.issue_keys)

    def test_estimate(self):
        s = self.planner.create_sprint("S")
        iss = self.client.create_issue("Task", project="P")
        self.planner.add_issue(s.id, iss.key)
        result = self.planner.estimate(iss.key, 5)
        self.assertEqual(result["points"], 5)
        self.assertEqual(result["sprint_id"], s.id)

    def test_estimate_with_sprint_id(self):
        s = self.planner.create_sprint("S")
        iss = self.client.create_issue("Task", project="P")
        self.planner.add_issue(s.id, iss.key)
        result = self.planner.estimate(iss.key, 8, sprint_id=s.id)
        self.assertEqual(result["points"], 8)

    def test_estimate_not_in_sprint(self):
        with self.assertRaises(KeyError):
            self.planner.estimate("NOPE-1", 3)

    def test_capacity(self):
        s = self.planner.create_sprint("S", capacity_points=20)
        i1 = self.client.create_issue("A", project="P")
        i2 = self.client.create_issue("B", project="P")
        self.planner.add_issue(s.id, i1.key)
        self.planner.add_issue(s.id, i2.key)
        self.planner.estimate(i1.key, 5, sprint_id=s.id)
        cap = self.planner.capacity(s.id)
        self.assertEqual(cap["capacity_points"], 20)
        self.assertEqual(cap["total_estimated"], 5)
        self.assertEqual(cap["remaining"], 15)
        self.assertEqual(cap["issue_count"], 2)
        self.assertEqual(cap["unestimated_count"], 1)

    def test_list_sprints(self):
        self.planner.create_sprint("A")
        s2 = self.planner.create_sprint("B")
        self.planner.start_sprint(s2.id)
        all_s = self.planner.list_sprints()
        self.assertEqual(len(all_s), 2)
        active = self.planner.list_sprints(status="active")
        self.assertEqual(len(active), 1)

    def test_sprint_issues(self):
        s = self.planner.create_sprint("S")
        i1 = self.client.create_issue("A", project="P")
        i2 = self.client.create_issue("B", project="P")
        self.planner.add_issue(s.id, i1.key)
        self.planner.add_issue(s.id, i2.key)
        issues = self.planner.sprint_issues(s.id)
        self.assertEqual(len(issues), 2)
