"""Tests for lidco.linear.dashboard."""
from __future__ import annotations

import time
import unittest

from lidco.linear.client import LinearClient
from lidco.linear.cycle import CyclePlanner
from lidco.linear.dashboard import LinearDashboard


class TestLinearDashboard(unittest.TestCase):
    def setUp(self):
        self.client = LinearClient()
        self.planner = CyclePlanner(self.client)
        self.dash = LinearDashboard(self.client, self.planner)

    def test_velocity_empty(self):
        vel = self.dash.velocity("Eng")
        self.assertEqual(vel, [])

    def test_velocity_with_cycles(self):
        now = time.time()
        c1 = self.planner.create_cycle("S1", now - 200, now - 100)
        c2 = self.planner.create_cycle("S2", now - 100, now)
        i1 = self.client.create_issue("A", "Eng")
        self.client.update_issue(i1.id, status="Done")
        self.planner.add_issue(c2.id, i1.id)
        vel = self.dash.velocity("Eng", cycles=5)
        self.assertEqual(len(vel), 2)
        # c2 is more recent
        self.assertEqual(vel[0]["completed"], 1)

    def test_velocity_limit(self):
        now = time.time()
        for n in range(5):
            self.planner.create_cycle(f"S{n}", now + n, now + n + 10)
        vel = self.dash.velocity("Eng", cycles=2)
        self.assertEqual(len(vel), 2)

    def test_distribution_empty(self):
        dist = self.dash.distribution("NoTeam")
        self.assertEqual(dist, {})

    def test_distribution_with_issues(self):
        self.client.create_issue("A", "TeamX")
        self.client.create_issue("B", "TeamX")
        i3 = self.client.create_issue("C", "TeamX")
        self.client.update_issue(i3.id, status="Done")
        dist = self.dash.distribution("TeamX")
        self.assertEqual(dist["Todo"], 2)
        self.assertEqual(dist["Done"], 1)

    def test_cycle_progress_empty(self):
        now = time.time()
        cycle = self.planner.create_cycle("S", now, now + 1000)
        prog = self.dash.cycle_progress(cycle.id)
        self.assertEqual(prog["total"], 0)
        self.assertEqual(prog["completed"], 0)
        self.assertEqual(prog["percent"], 0.0)

    def test_cycle_progress_with_issues(self):
        now = time.time()
        cycle = self.planner.create_cycle("S", now, now + 10000)
        i1 = self.client.create_issue("A", "E")
        i2 = self.client.create_issue("B", "E")
        self.client.update_issue(i1.id, status="Done")
        self.planner.add_issue(cycle.id, i1.id)
        self.planner.add_issue(cycle.id, i2.id)
        prog = self.dash.cycle_progress(cycle.id)
        self.assertEqual(prog["total"], 2)
        self.assertEqual(prog["completed"], 1)
        self.assertEqual(prog["percent"], 50.0)
        self.assertGreater(prog["time_remaining_s"], 0)

    def test_cycle_progress_not_found(self):
        with self.assertRaises(KeyError):
            self.dash.cycle_progress("nonexistent")

    def test_sla_tracking_empty(self):
        sla = self.dash.sla_tracking("NoTeam")
        self.assertEqual(sla, [])

    def test_sla_tracking_within(self):
        issue = self.client.create_issue("X", "T1", priority=1)
        sla = self.dash.sla_tracking("T1")
        self.assertEqual(len(sla), 1)
        self.assertTrue(sla[0]["within_sla"])
        self.assertEqual(sla[0]["sla_hours"], 72.0)

    def test_sla_tracking_high_priority(self):
        issue = self.client.create_issue("U", "T2", priority=3)
        sla = self.dash.sla_tracking("T2")
        self.assertEqual(sla[0]["sla_hours"], 24.0)

    def test_sla_tracking_excludes_done(self):
        i = self.client.create_issue("D", "T3")
        self.client.update_issue(i.id, status="Done")
        sla = self.dash.sla_tracking("T3")
        self.assertEqual(len(sla), 0)

    def test_client_property(self):
        self.assertIs(self.dash.client, self.client)

    def test_planner_property(self):
        self.assertIs(self.dash.planner, self.planner)


if __name__ == "__main__":
    unittest.main()
