"""Tests for budget.history."""
from __future__ import annotations

import unittest

from lidco.budget.history import BudgetHistory, BudgetSnapshot


class TestBudgetSnapshot(unittest.TestCase):
    def test_frozen(self) -> None:
        snap = BudgetSnapshot(session_id="s1")
        with self.assertRaises(AttributeError):
            snap.session_id = "s2"  # type: ignore[misc]

    def test_defaults(self) -> None:
        snap = BudgetSnapshot(session_id="s1")
        self.assertEqual(snap.model, "")
        self.assertEqual(snap.total_tokens, 0)
        self.assertEqual(snap.context_limit, 128000)
        self.assertEqual(snap.turns, 0)
        self.assertEqual(snap.compactions, 0)
        self.assertEqual(snap.efficiency, 0.0)
        self.assertEqual(snap.cost, 0.0)
        self.assertIsInstance(snap.timestamp, float)


class TestBudgetHistory(unittest.TestCase):
    def setUp(self) -> None:
        self.history = BudgetHistory(max_entries=5)

    def test_record_returns_snapshot(self) -> None:
        snap = self.history.record("s1", model="gpt-4", total_tokens=1000)
        self.assertIsInstance(snap, BudgetSnapshot)
        self.assertEqual(snap.session_id, "s1")
        self.assertEqual(snap.model, "gpt-4")

    def test_max_entries_enforced(self) -> None:
        for i in range(10):
            self.history.record(f"s{i}")
        self.assertEqual(len(self.history.export()), 5)

    def test_query_filters_by_model(self) -> None:
        self.history.record("s1", model="gpt-4", efficiency=0.5)
        self.history.record("s2", model="claude", efficiency=0.7)
        results = self.history.query(model="claude")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].model, "claude")

    def test_query_filters_by_min_efficiency(self) -> None:
        self.history.record("s1", efficiency=0.3)
        self.history.record("s2", efficiency=0.8)
        results = self.history.query(min_efficiency=0.5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].efficiency, 0.8)

    def test_get_by_session(self) -> None:
        self.history.record("s1", model="a")
        self.history.record("s2", model="b")
        snap = self.history.get_by_session("s1")
        self.assertIsNotNone(snap)
        self.assertEqual(snap.session_id, "s1")  # type: ignore[union-attr]

    def test_get_by_session_missing(self) -> None:
        self.assertIsNone(self.history.get_by_session("nope"))

    def test_average_efficiency(self) -> None:
        self.history.record("s1", efficiency=0.4)
        self.history.record("s2", efficiency=0.8)
        self.assertAlmostEqual(self.history.average_efficiency(), 0.6)

    def test_average_efficiency_empty(self) -> None:
        self.assertEqual(self.history.average_efficiency(), 0.0)

    def test_total_cost(self) -> None:
        self.history.record("s1", cost=0.05)
        self.history.record("s2", cost=0.10)
        self.assertAlmostEqual(self.history.total_cost(), 0.15)

    def test_total_cost_filtered(self) -> None:
        self.history.record("s1", model="a", cost=0.05)
        self.history.record("s2", model="b", cost=0.10)
        self.assertAlmostEqual(self.history.total_cost(model="a"), 0.05)

    def test_trend(self) -> None:
        for i in range(5):
            self.history.record(f"s{i}")
        trend = self.history.trend(last_n=3)
        self.assertEqual(len(trend), 3)
        self.assertEqual(trend[-1].session_id, "s4")

    def test_clear(self) -> None:
        self.history.record("s1")
        self.history.clear()
        self.assertEqual(len(self.history.export()), 0)

    def test_export(self) -> None:
        self.history.record("s1", model="m")
        data = self.history.export()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["session_id"], "s1")
        self.assertIn("timestamp", data[0])

    def test_summary_empty(self) -> None:
        self.assertIn("No budget history", self.history.summary())

    def test_summary_with_data(self) -> None:
        self.history.record("s1", efficiency=0.5, cost=0.01)
        s = self.history.summary()
        self.assertIn("1 snapshots", s)
        self.assertIn("avg efficiency", s)


if __name__ == "__main__":
    unittest.main()
