"""Tests for lidco.enterprise.aggregator."""
from __future__ import annotations

import json
import unittest

from lidco.enterprise.aggregator import UsageAggregator, UsageEntry


class TestUsageEntry(unittest.TestCase):
    def test_frozen(self) -> None:
        e = UsageEntry(instance_id="i1", team="t", project="p", tokens=100, cost=1.0, timestamp=0.0)
        with self.assertRaises(AttributeError):
            e.tokens = 200  # type: ignore[misc]


class TestUsageAggregator(unittest.TestCase):
    def setUp(self) -> None:
        self.agg = UsageAggregator()

    def test_record(self) -> None:
        entry = self.agg.record("i1", "eng", "proj-a", 1000, 5.0)
        self.assertEqual(entry.team, "eng")
        self.assertEqual(len(self.agg.entries()), 1)

    def test_by_team(self) -> None:
        self.agg.record("i1", "eng", "p1", 100, 1.0)
        self.agg.record("i2", "eng", "p2", 200, 2.0)
        self.agg.record("i3", "ops", "p1", 50, 0.5)
        teams = self.agg.by_team()
        self.assertEqual(teams["eng"]["tokens"], 300)
        self.assertEqual(teams["ops"]["cost"], 0.5)

    def test_by_project(self) -> None:
        self.agg.record("i1", "eng", "alpha", 100, 1.0)
        self.agg.record("i2", "ops", "alpha", 200, 2.0)
        projects = self.agg.by_project()
        self.assertEqual(projects["alpha"]["tokens"], 300)

    def test_by_instance(self) -> None:
        self.agg.record("i1", "eng", "p1", 100, 1.0)
        self.agg.record("i1", "eng", "p2", 200, 2.0)
        instances = self.agg.by_instance()
        self.assertEqual(instances["i1"]["tokens"], 300)

    def test_total(self) -> None:
        self.agg.record("i1", "eng", "p1", 100, 1.0)
        self.agg.record("i2", "ops", "p2", 200, 2.0)
        t = self.agg.total()
        self.assertEqual(t["tokens"], 300)
        self.assertAlmostEqual(t["cost"], 3.0)
        self.assertEqual(t["entry_count"], 2)

    def test_top_teams(self) -> None:
        self.agg.record("i1", "eng", "p1", 100, 10.0)
        self.agg.record("i2", "ops", "p2", 200, 5.0)
        top = self.agg.top_teams(limit=1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0][0], "eng")

    def test_export_json(self) -> None:
        self.agg.record("i1", "eng", "p1", 100, 1.0)
        data = json.loads(self.agg.export("json"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["tokens"], 100)

    def test_export_csv(self) -> None:
        self.agg.record("i1", "eng", "p1", 100, 1.0)
        csv = self.agg.export("csv")
        self.assertIn("instance_id,team,project,tokens,cost,timestamp", csv)
        self.assertIn("i1", csv)

    def test_summary(self) -> None:
        self.agg.record("i1", "eng", "p1", 100, 1.0)
        s = self.agg.summary()
        self.assertEqual(s["entry_count"], 1)
        self.assertEqual(s["teams"], 1)

    def test_empty(self) -> None:
        self.assertEqual(self.agg.total()["tokens"], 0)
        self.assertEqual(self.agg.top_teams(), [])


if __name__ == "__main__":
    unittest.main()
