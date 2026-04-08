"""Tests for lidco.cloudcost.forecaster — CostForecaster."""

from __future__ import annotations

import unittest

from lidco.cloudcost.forecaster import (
    BudgetAlert,
    CostDataPoint,
    CostForecast,
    CostForecaster,
    SeasonalPattern,
)


class TestCostDataPoint(unittest.TestCase):
    def test_frozen(self) -> None:
        p = CostDataPoint(date="2026-01", amount=100.0)
        self.assertEqual(p.date, "2026-01")
        with self.assertRaises(AttributeError):
            p.amount = 200.0  # type: ignore[misc]


class TestCostForecaster(unittest.TestCase):
    def test_empty_forecast(self) -> None:
        f = CostForecaster()
        result = f.forecast()
        self.assertIsInstance(result, CostForecast)
        self.assertEqual(result.current_monthly, 0.0)
        self.assertEqual(result.trend_direction, "stable")
        self.assertEqual(result.forecast_points, [])

    def test_single_point(self) -> None:
        f = CostForecaster()
        f.add_data([CostDataPoint("2026-01", 500.0)])
        result = f.forecast(periods=2)
        self.assertEqual(result.current_monthly, 500.0)
        # With one point, slope=0 so projected == current
        self.assertEqual(result.projected_monthly, 500.0)

    def test_upward_trend(self) -> None:
        f = CostForecaster()
        f.add_data([
            CostDataPoint("2026-01", 100.0),
            CostDataPoint("2026-02", 200.0),
            CostDataPoint("2026-03", 300.0),
        ])
        result = f.forecast(periods=3)
        self.assertEqual(result.trend_direction, "up")
        self.assertGreater(result.projected_monthly, 300.0)
        self.assertGreater(result.trend_pct, 0)

    def test_downward_trend(self) -> None:
        f = CostForecaster()
        f.add_data([
            CostDataPoint("2026-01", 300.0),
            CostDataPoint("2026-02", 200.0),
            CostDataPoint("2026-03", 100.0),
        ])
        result = f.forecast(periods=3)
        self.assertEqual(result.trend_direction, "down")
        self.assertLess(result.trend_pct, 0)

    def test_stable_trend(self) -> None:
        f = CostForecaster()
        f.add_data([
            CostDataPoint("2026-01", 100.0),
            CostDataPoint("2026-02", 100.0),
            CostDataPoint("2026-03", 100.0),
        ])
        result = f.forecast(periods=1)
        self.assertEqual(result.trend_direction, "stable")
        self.assertEqual(result.trend_pct, 0.0)

    def test_forecast_points_count(self) -> None:
        f = CostForecaster()
        f.add_data([
            CostDataPoint("2026-01", 100.0),
            CostDataPoint("2026-02", 150.0),
        ])
        result = f.forecast(periods=5)
        self.assertEqual(len(result.forecast_points), 5)
        self.assertEqual(result.forecast_points[0].date, "T+1")
        self.assertEqual(result.forecast_points[4].date, "T+5")

    def test_budget_alert_triggered(self) -> None:
        f = CostForecaster(budget=200.0)
        f.add_data([
            CostDataPoint("2026-01", 100.0),
            CostDataPoint("2026-02", 200.0),
            CostDataPoint("2026-03", 300.0),
        ])
        result = f.forecast(periods=1)
        self.assertGreater(len(result.alerts), 0)
        alert = result.alerts[0]
        self.assertIsInstance(alert, BudgetAlert)
        self.assertGreater(alert.overage, 0)
        self.assertIn("exceeds budget", alert.message)

    def test_no_budget_alert_when_under(self) -> None:
        f = CostForecaster(budget=10000.0)
        f.add_data([
            CostDataPoint("2026-01", 100.0),
            CostDataPoint("2026-02", 100.0),
        ])
        result = f.forecast(periods=1)
        self.assertEqual(len(result.alerts), 0)

    def test_no_budget_no_alerts(self) -> None:
        f = CostForecaster()
        f.add_data([CostDataPoint("2026-01", 100.0)])
        result = f.forecast()
        self.assertEqual(result.alerts, [])

    def test_seasonal_detection_requires_data(self) -> None:
        f = CostForecaster()
        f.add_data([CostDataPoint("m1", 100.0), CostDataPoint("m2", 200.0)])
        result = f.forecast()
        self.assertIsNone(result.seasonal)

    def test_seasonal_detection_with_enough_data(self) -> None:
        f = CostForecaster()
        data = [
            CostDataPoint(f"m{i}", 100.0 + (50.0 if i % 3 == 0 else 0.0))
            for i in range(8)
        ]
        f.add_data(data)
        result = f.forecast()
        if result.seasonal:
            self.assertIsInstance(result.seasonal, SeasonalPattern)
            self.assertGreater(result.seasonal.amplitude, 0)

    def test_linear_regression_flat(self) -> None:
        slope, intercept = CostForecaster._linear_regression([5.0, 5.0, 5.0])
        self.assertAlmostEqual(slope, 0.0)
        self.assertAlmostEqual(intercept, 5.0)

    def test_linear_regression_upward(self) -> None:
        slope, intercept = CostForecaster._linear_regression([1.0, 2.0, 3.0])
        self.assertAlmostEqual(slope, 1.0, places=2)
        self.assertAlmostEqual(intercept, 1.0, places=2)

    def test_immutable_data(self) -> None:
        f = CostForecaster()
        original = [CostDataPoint("m1", 100.0)]
        f.add_data(original)
        f.add_data([CostDataPoint("m2", 200.0)])
        self.assertEqual(len(original), 1)


if __name__ == "__main__":
    unittest.main()
