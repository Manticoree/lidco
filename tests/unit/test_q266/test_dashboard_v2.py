"""Tests for lidco.enterprise.dashboard_v2."""
from __future__ import annotations

import unittest

from lidco.enterprise.aggregator import UsageAggregator
from lidco.enterprise.dashboard_v2 import EnterpriseDashboard, OrgMetrics
from lidco.enterprise.fleet import FleetManager


class TestEnterpriseDashboard(unittest.TestCase):
    def setUp(self) -> None:
        self.fleet = FleetManager()
        self.agg = UsageAggregator()
        self.dash = EnterpriseDashboard(self.fleet, self.agg)

    def test_empty_adoption_rate(self) -> None:
        self.assertEqual(self.dash.adoption_rate(), 0.0)

    def test_adoption_rate(self) -> None:
        self.fleet.register("a", "1.0")
        inst = self.fleet.register("b", "1.0")
        inst.status = "offline"
        self.assertAlmostEqual(self.dash.adoption_rate(), 0.5)

    def test_roi_estimate_no_cost(self) -> None:
        self.agg.record("i1", "eng", "p1", 10000, 0.0)
        roi = self.dash.roi_estimate(developer_hourly_rate=100.0, hours_saved_per_1k_tokens=0.1)
        self.assertGreater(roi, 0)

    def test_roi_estimate_with_cost(self) -> None:
        self.agg.record("i1", "eng", "p1", 10000, 50.0)
        roi = self.dash.roi_estimate(developer_hourly_rate=100.0, hours_saved_per_1k_tokens=0.1)
        # 10000/1000 * 0.1 * 100 - 50 = 100 - 50 = 50
        self.assertAlmostEqual(roi, 50.0)

    def test_metrics(self) -> None:
        self.fleet.register("a", "1.0")
        self.agg.record("i1", "eng", "p1", 1000, 5.0)
        m = self.dash.metrics()
        self.assertIsInstance(m, OrgMetrics)
        self.assertEqual(m.total_instances, 1)
        self.assertEqual(m.total_tokens, 1000)

    def test_executive_summary(self) -> None:
        self.fleet.register("a", "1.0")
        self.agg.record("i1", "eng", "p1", 1000, 5.0)
        s = self.dash.executive_summary()
        self.assertIn("Fleet:", s)
        self.assertIn("1 instances", s)

    def test_render_text(self) -> None:
        self.fleet.register("a", "1.0")
        text = self.dash.render_text()
        self.assertIn("Enterprise Dashboard", text)
        self.assertIn("Instances:", text)

    def test_summary_dict(self) -> None:
        self.fleet.register("a", "1.0")
        s = self.dash.summary()
        self.assertIn("total_instances", s)
        self.assertIn("roi_estimate", s)

    def test_org_metrics_frozen(self) -> None:
        m = OrgMetrics(1, 1, 1, 100, 1.0, 1.0, 10.0)
        with self.assertRaises(AttributeError):
            m.total_instances = 5  # type: ignore[misc]

    def test_multiple_teams_counted(self) -> None:
        self.fleet.register("a", "1.0")
        self.agg.record("i1", "eng", "p1", 100, 1.0)
        self.agg.record("i2", "ops", "p2", 200, 2.0)
        m = self.dash.metrics()
        self.assertEqual(m.total_users, 2)


if __name__ == "__main__":
    unittest.main()
