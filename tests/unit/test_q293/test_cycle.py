"""Tests for lidco.linear.cycle."""
from __future__ import annotations

import time
import unittest

from lidco.linear.client import LinearClient
from lidco.linear.cycle import Cycle, CyclePlanner


class TestCycleDataclass(unittest.TestCase):
    def test_defaults(self):
        c = Cycle(id="c1", name="Sprint 1", start=100.0, end=200.0)
        self.assertEqual(c.issue_ids, [])

    def test_custom_issues(self):
        c = Cycle(id="c1", name="S", start=0, end=1, issue_ids=["a", "b"])
        self.assertEqual(len(c.issue_ids), 2)


class TestCyclePlanner(unittest.TestCase):
    def setUp(self):
        self.client = LinearClient()
        self.planner = CyclePlanner(self.client)

    def test_create_cycle(self):
        now = time.time()
        cycle = self.planner.create_cycle("Sprint 1", now, now + 86400)
        self.assertTrue(cycle.id.startswith("CYC-"))
        self.assertEqual(cycle.name, "Sprint 1")

    def test_create_cycle_empty_name(self):
        with self.assertRaises(ValueError):
            self.planner.create_cycle("", 0, 1)

    def test_create_cycle_invalid_dates(self):
        with self.assertRaises(ValueError):
            self.planner.create_cycle("S", 100, 50)

    def test_get_cycle(self):
        cycle = self.planner.create_cycle("S", 0, 100)
        fetched = self.planner.get_cycle(cycle.id)
        self.assertEqual(fetched.name, "S")

    def test_get_cycle_not_found(self):
        with self.assertRaises(KeyError):
            self.planner.get_cycle("nonexistent")

    def test_add_issue(self):
        cycle = self.planner.create_cycle("S", 0, 100)
        issue = self.client.create_issue("Bug", "Eng")
        self.planner.add_issue(cycle.id, issue.id)
        self.assertIn(issue.id, cycle.issue_ids)

    def test_add_issue_duplicate_ignored(self):
        cycle = self.planner.create_cycle("S", 0, 100)
        issue = self.client.create_issue("B", "E")
        self.planner.add_issue(cycle.id, issue.id)
        self.planner.add_issue(cycle.id, issue.id)
        self.assertEqual(len(cycle.issue_ids), 1)

    def test_add_issue_nonexistent_issue(self):
        cycle = self.planner.create_cycle("S", 0, 100)
        with self.assertRaises(KeyError):
            self.planner.add_issue(cycle.id, "fake-id")

    def test_scope_empty(self):
        cycle = self.planner.create_cycle("S", 0, 100)
        scope = self.planner.scope(cycle.id)
        self.assertEqual(scope["total"], 0)
        self.assertEqual(scope["by_status"], {})

    def test_scope_with_issues(self):
        cycle = self.planner.create_cycle("S", 0, 100)
        i1 = self.client.create_issue("A", "E")
        i2 = self.client.create_issue("B", "E")
        self.client.update_issue(i2.id, status="Done")
        self.planner.add_issue(cycle.id, i1.id)
        self.planner.add_issue(cycle.id, i2.id)
        scope = self.planner.scope(cycle.id)
        self.assertEqual(scope["total"], 2)
        self.assertEqual(scope["by_status"]["Todo"], 1)
        self.assertEqual(scope["by_status"]["Done"], 1)

    def test_estimates_empty(self):
        cycle = self.planner.create_cycle("S", 0, 100)
        est = self.planner.estimates(cycle.id)
        self.assertEqual(est["total_points"], 0)
        self.assertEqual(est["avg_priority"], 0.0)

    def test_estimates_with_issues(self):
        cycle = self.planner.create_cycle("S", 0, 100)
        i1 = self.client.create_issue("A", "E", priority=3)
        i2 = self.client.create_issue("B", "E", priority=5)
        self.planner.add_issue(cycle.id, i1.id)
        self.planner.add_issue(cycle.id, i2.id)
        est = self.planner.estimates(cycle.id)
        self.assertEqual(est["total_points"], 8)
        self.assertEqual(est["avg_priority"], 4.0)
        self.assertEqual(len(est["items"]), 2)

    def test_client_property(self):
        self.assertIs(self.planner.client, self.client)


if __name__ == "__main__":
    unittest.main()
