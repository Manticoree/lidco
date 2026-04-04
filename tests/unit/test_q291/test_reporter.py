"""Tests for lidco.jira.reporter."""
from __future__ import annotations

import unittest

from lidco.jira.client import JiraClient
from lidco.jira.sprint import SprintPlanner
from lidco.jira.reporter import JiraReporter, VelocityEntry


class TestVelocityEntry(unittest.TestCase):
    def test_defaults(self):
        v = VelocityEntry(sprint_id="s-1", sprint_name="Sprint 1")
        self.assertEqual(v.committed, 0)
        self.assertEqual(v.completed, 0)


class TestJiraReporter(unittest.TestCase):
    def setUp(self):
        self.client = JiraClient()
        self.client.add_project("P", "Project")
        self.planner = SprintPlanner(self.client)
        self.reporter = JiraReporter(self.planner)

    def test_planner_property(self):
        self.assertIs(self.reporter.planner, self.planner)

    def _make_closed_sprint(self, name: str, issues_done: int = 0, issues_total: int = 2, pts: int = 5):
        """Helper: create a closed sprint with some done issues."""
        s = self.planner.create_sprint(name, capacity_points=pts * issues_total)
        for i in range(issues_total):
            iss = self.client.create_issue(f"{name}-{i}", project="P")
            self.planner.add_issue(s.id, iss.key)
            self.planner.estimate(iss.key, pts, sprint_id=s.id)
            if i < issues_done:
                self.client.update_issue(iss.key, status="Done")
        self.planner.start_sprint(s.id)
        self.planner.close_sprint(s.id)
        return s

    def test_velocity_empty(self):
        vel = self.reporter.velocity()
        self.assertEqual(len(vel), 0)

    def test_velocity_closed(self):
        self._make_closed_sprint("S1", issues_done=1, issues_total=2, pts=3)
        vel = self.reporter.velocity()
        self.assertEqual(len(vel), 1)
        self.assertEqual(vel[0].committed, 6)
        self.assertEqual(vel[0].completed, 3)

    def test_velocity_specific_sprints(self):
        s1 = self._make_closed_sprint("S1", issues_done=2, issues_total=2, pts=5)
        s2 = self._make_closed_sprint("S2", issues_done=1, issues_total=2, pts=3)
        vel = self.reporter.velocity(sprints=[s1.id])
        self.assertEqual(len(vel), 1)
        self.assertEqual(vel[0].completed, 10)

    def test_burndown_empty_sprint(self):
        s = self.planner.create_sprint("Empty")
        data = self.reporter.burndown(s.id)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["remaining_points"], 0)

    def test_burndown_with_progress(self):
        s = self.planner.create_sprint("B")
        i1 = self.client.create_issue("a", project="P")
        i2 = self.client.create_issue("b", project="P")
        self.planner.add_issue(s.id, i1.key)
        self.planner.add_issue(s.id, i2.key)
        self.planner.estimate(i1.key, 5, sprint_id=s.id)
        self.planner.estimate(i2.key, 3, sprint_id=s.id)
        self.client.update_issue(i1.key, status="Done")
        data = self.reporter.burndown(s.id)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["remaining_points"], 8)
        self.assertEqual(data[1]["remaining_points"], 3)
        self.assertEqual(data[1]["completed_points"], 5)

    def test_burndown_not_found(self):
        with self.assertRaises(KeyError):
            self.reporter.burndown("nope")

    def test_completion_prediction(self):
        s = self.planner.create_sprint("Pred", capacity_points=20)
        i1 = self.client.create_issue("a", project="P")
        i2 = self.client.create_issue("b", project="P")
        self.planner.add_issue(s.id, i1.key)
        self.planner.add_issue(s.id, i2.key)
        self.planner.estimate(i1.key, 5, sprint_id=s.id)
        self.planner.estimate(i2.key, 3, sprint_id=s.id)
        self.client.update_issue(i1.key, status="Done")
        pred = self.reporter.completion_prediction(s.id)
        self.assertEqual(pred["total_points"], 8)
        self.assertEqual(pred["completed_points"], 5)
        self.assertEqual(pred["remaining_points"], 3)
        self.assertIn("avg_velocity", pred)
        self.assertIn("on_track", pred)

    def test_completion_prediction_with_history(self):
        # Create a closed sprint for historical velocity
        self._make_closed_sprint("Past", issues_done=2, issues_total=2, pts=5)
        # Active sprint
        s = self.planner.create_sprint("Current")
        iss = self.client.create_issue("c", project="P")
        self.planner.add_issue(s.id, iss.key)
        self.planner.estimate(iss.key, 3, sprint_id=s.id)
        pred = self.reporter.completion_prediction(s.id)
        self.assertEqual(pred["remaining_points"], 3)
        self.assertEqual(pred["avg_velocity"], 10)  # 2*5 from closed sprint

    def test_summary_empty(self):
        s = self.reporter.summary()
        self.assertEqual(s["total_sprints"], 0)
        self.assertEqual(s["average_velocity"], 0)

    def test_summary_with_data(self):
        self._make_closed_sprint("S1", issues_done=1, issues_total=2, pts=4)
        self.planner.create_sprint("S2")
        s = self.reporter.summary()
        self.assertEqual(s["total_sprints"], 2)
        self.assertEqual(s["closed_sprints"], 1)
        self.assertEqual(s["future_sprints"], 1)
        self.assertEqual(s["total_committed"], 8)
        self.assertEqual(s["total_completed"], 4)
        self.assertEqual(s["average_velocity"], 4)
