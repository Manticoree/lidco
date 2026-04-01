"""Tests for budget.usage_dashboard — TurnUsage & UsageDashboard."""
from __future__ import annotations

import unittest

from lidco.budget.usage_dashboard import TurnUsage, UsageDashboard


class TestTurnUsage(unittest.TestCase):
    def test_frozen(self):
        tu = TurnUsage(turn=1, used=100)
        with self.assertRaises(AttributeError):
            tu.used = 200  # type: ignore[misc]

    def test_defaults(self):
        tu = TurnUsage(turn=1, used=100)
        self.assertEqual(tu.delta, 0)
        self.assertEqual(tu.role_breakdown, ())


class TestUsageDashboard(unittest.TestCase):
    def setUp(self):
        self.db = UsageDashboard()

    def test_record_turn(self):
        entry = self.db.record_turn(1, 5000)
        self.assertEqual(entry.turn, 1)
        self.assertEqual(entry.used, 5000)
        self.assertEqual(entry.delta, 0)  # first turn has 0 delta

    def test_delta_calculated(self):
        self.db.record_turn(1, 5000)
        entry = self.db.record_turn(2, 8000)
        self.assertEqual(entry.delta, 3000)

    def test_get_trend(self):
        for i in range(1, 16):
            self.db.record_turn(i, i * 1000)
        trend = self.db.get_trend(5)
        self.assertEqual(len(trend), 5)
        self.assertEqual(trend[0].turn, 11)

    def test_average_per_turn(self):
        self.db.record_turn(1, 1000)
        self.db.record_turn(2, 3000)
        self.assertAlmostEqual(self.db.average_per_turn(), 2000.0)

    def test_average_empty(self):
        self.assertAlmostEqual(self.db.average_per_turn(), 0.0)

    def test_peak(self):
        self.db.record_turn(1, 5000)
        self.db.record_turn(2, 9000)
        self.db.record_turn(3, 7000)
        pk = self.db.peak()
        self.assertIsNotNone(pk)
        self.assertEqual(pk.turn, 2)
        self.assertEqual(pk.used, 9000)

    def test_peak_empty(self):
        self.assertIsNone(self.db.peak())

    def test_burn_rate(self):
        self.db.record_turn(1, 1000)
        self.db.record_turn(2, 3000)
        self.db.record_turn(3, 6000)
        # deltas: 2000, 3000 -> avg 2500
        self.assertAlmostEqual(self.db.burn_rate(), 2500.0)

    def test_format_bar(self):
        bar = self.db.format_bar(50, 100, width=10)
        self.assertIn("50.0%", bar)
        self.assertIn("█", bar)
        self.assertIn("░", bar)

    def test_format_bar_zero_total(self):
        bar = self.db.format_bar(10, 0, width=10)
        self.assertIn("0.0%", bar)

    def test_summary_empty(self):
        s = self.db.summary()
        self.assertIn("No data", s)

    def test_summary_with_data(self):
        self.db.record_turn(1, 5000)
        self.db.record_turn(2, 12000)
        s = self.db.summary(context_limit=200000)
        self.assertIn("Usage Dashboard", s)
        self.assertIn("Tokens:", s)
        self.assertIn("Burn rate:", s)

    def test_breakdown_recorded(self):
        entry = self.db.record_turn(1, 5000, breakdown={"user": 3000, "system": 2000})
        self.assertEqual(len(entry.role_breakdown), 2)


if __name__ == "__main__":
    unittest.main()
