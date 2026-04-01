"""Tests for budget.window_meter — TokenAccount, WindowSnapshot, ContextWindowMeter."""
from __future__ import annotations

import unittest

from lidco.budget.window_meter import ContextWindowMeter, TokenAccount, WindowSnapshot


class TestTokenAccount(unittest.TestCase):
    def test_frozen(self):
        ta = TokenAccount(role="user", tokens=100)
        with self.assertRaises(AttributeError):
            ta.tokens = 200  # type: ignore[misc]

    def test_defaults(self):
        ta = TokenAccount(role="system")
        self.assertEqual(ta.tokens, 0)
        self.assertEqual(ta.message_count, 0)


class TestWindowSnapshot(unittest.TestCase):
    def test_defaults(self):
        snap = WindowSnapshot()
        self.assertEqual(snap.used, 0)
        self.assertEqual(snap.limit, 128000)
        self.assertEqual(snap.accounts, ())
        self.assertEqual(snap.turn, 0)


class TestContextWindowMeter(unittest.TestCase):
    def setUp(self):
        self.meter = ContextWindowMeter(context_limit=200000)

    def test_initial_state(self):
        self.assertEqual(self.meter.used, 0)
        self.assertEqual(self.meter.remaining, 200000)
        self.assertAlmostEqual(self.meter.utilization(), 0.0)

    def test_record_adds_tokens(self):
        self.meter.record("system", 3000)
        self.meter.record("user", 5000)
        self.assertEqual(self.meter.used, 8000)

    def test_record_user_increments_turn(self):
        self.meter.record("user", 100)
        self.meter.record("user", 200)
        snap = self.meter.snapshot()
        self.assertEqual(snap.turn, 2)

    def test_remove_tokens(self):
        self.meter.record("assistant", 10000)
        self.meter.remove("assistant", 3000)
        self.assertEqual(self.meter.used, 7000)

    def test_remove_floors_at_zero(self):
        self.meter.record("tool", 100)
        self.meter.remove("tool", 500)
        self.assertEqual(self.meter.used, 0)

    def test_utilization(self):
        self.meter.record("user", 100000)
        self.assertAlmostEqual(self.meter.utilization(), 0.5)
        self.assertAlmostEqual(self.meter.percentage(), 50.0)

    def test_remaining(self):
        self.meter.record("system", 150000)
        self.assertEqual(self.meter.remaining, 50000)

    def test_snapshot(self):
        self.meter.record("system", 3200)
        self.meter.record("user", 12000)
        snap = self.meter.snapshot()
        self.assertEqual(snap.used, 15200)
        self.assertEqual(snap.limit, 200000)
        self.assertEqual(len(snap.accounts), 2)

    def test_get_breakdown(self):
        self.meter.record("system", 1000)
        self.meter.record("user", 2000)
        bd = self.meter.get_breakdown()
        self.assertEqual(bd["system"], 1000)
        self.assertEqual(bd["user"], 2000)

    def test_peak_usage(self):
        self.meter.record("user", 50000)
        self.meter.record("assistant", 30000)
        self.meter.remove("user", 20000)
        self.assertEqual(self.meter.peak_usage(), 80000)

    def test_reset(self):
        self.meter.record("user", 5000)
        self.meter.reset()
        self.assertEqual(self.meter.used, 0)
        self.assertEqual(self.meter.peak_usage(), 0)

    def test_summary(self):
        self.meter.record("system", 3200)
        self.meter.record("user", 12030)
        s = self.meter.summary()
        self.assertIn("Context:", s)
        self.assertIn("system:", s)
        self.assertIn("user:", s)


if __name__ == "__main__":
    unittest.main()
