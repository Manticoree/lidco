"""Tests for budget.budget_forecaster."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.budget.budget_forecaster import BudgetForecaster, Forecast


class TestForecast(unittest.TestCase):
    def test_frozen(self):
        f = Forecast()
        with self.assertRaises(AttributeError):
            f.current_used = 99  # type: ignore[misc]

    def test_defaults(self):
        f = Forecast()
        self.assertEqual(f.current_used, 0)
        self.assertEqual(f.total_budget, 128_000)
        self.assertEqual(f.recommendation, "")


class TestBudgetForecaster(unittest.TestCase):
    def test_no_samples(self):
        fc = BudgetForecaster()
        self.assertAlmostEqual(fc.burn_rate(), 0.0)
        self.assertEqual(fc.turns_remaining(), 0)

    def test_record_and_burn_rate(self):
        fc = BudgetForecaster(total_budget=10000)
        t = 1000.0
        with patch("lidco.budget.budget_forecaster.time") as mock_time:
            mock_time.monotonic = lambda: t
            fc.record(0)
            t = 1001.0
            mock_time.monotonic = lambda: t
            fc.record(1000)
        self.assertAlmostEqual(fc.burn_rate(), 1000.0)

    def test_turns_remaining(self):
        fc = BudgetForecaster(total_budget=10000)
        t = 100.0
        with patch("lidco.budget.budget_forecaster.time") as mock_time:
            for i in range(5):
                mock_time.monotonic = lambda _i=i: 100.0 + _i
                fc.record(i * 1000)
        # 4000 used, 6000 remaining, ~1000/turn → 6
        turns = fc.turns_remaining()
        self.assertGreater(turns, 0)

    def test_forecast_ok(self):
        fc = BudgetForecaster(total_budget=100000)
        t = 0.0
        with patch("lidco.budget.budget_forecaster.time") as mock_time:
            for i in range(30):
                mock_time.monotonic = lambda _i=i: float(_i)
                fc.record(i * 100)
        f = fc.forecast()
        self.assertEqual(f.recommendation, "OK")

    def test_forecast_compact_now(self):
        fc = BudgetForecaster(total_budget=5000)
        t = 0.0
        with patch("lidco.budget.budget_forecaster.time") as mock_time:
            for i in range(5):
                mock_time.monotonic = lambda _i=i: float(_i)
                fc.record(i * 1000)
        f = fc.forecast()
        self.assertIn(f.recommendation, ("Compact now", "Over budget"))

    def test_forecast_over_budget(self):
        fc = BudgetForecaster(total_budget=100)
        with patch("lidco.budget.budget_forecaster.time") as mock_time:
            mock_time.monotonic = lambda: 0.0
            fc.record(100)
        f = fc.forecast()
        self.assertEqual(f.recommendation, "Over budget")

    def test_time_to_depletion_no_data(self):
        fc = BudgetForecaster()
        self.assertAlmostEqual(fc.time_to_depletion(), 0.0)

    def test_time_to_depletion_with_data(self):
        fc = BudgetForecaster(total_budget=10000)
        with patch("lidco.budget.budget_forecaster.time") as mock_time:
            mock_time.monotonic = lambda: 0.0
            fc.record(0)
            mock_time.monotonic = lambda: 10.0
            fc.record(5000)
        ttd = fc.time_to_depletion()
        # 5000 remaining / 500 tok/s = 10s
        self.assertAlmostEqual(ttd, 10.0)

    def test_summary(self):
        fc = BudgetForecaster()
        text = fc.summary()
        self.assertIn("BudgetForecast", text)

    def test_turns_with_explicit_tokens_per_turn(self):
        fc = BudgetForecaster(total_budget=10000)
        with patch("lidco.budget.budget_forecaster.time") as mock_time:
            mock_time.monotonic = lambda: 0.0
            fc.record(2000)
        turns = fc.turns_remaining(tokens_per_turn=1000.0)
        self.assertEqual(turns, 8)


if __name__ == "__main__":
    unittest.main()
