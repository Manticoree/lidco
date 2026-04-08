"""Tests for lidco.cloudcost.dashboard — CostDashboard."""

from __future__ import annotations

import unittest

from lidco.cloudcost.dashboard import (
    Anomaly,
    CostDashboard,
    DashboardReport,
    EnvironmentCost,
    TagGroup,
    TrendPoint,
)


class TestTrendPoint(unittest.TestCase):
    def test_frozen(self) -> None:
        p = TrendPoint(label="2026-01", amount=100.0)
        self.assertEqual(p.label, "2026-01")
        with self.assertRaises(AttributeError):
            p.amount = 0.0  # type: ignore[misc]


class TestCostDashboard(unittest.TestCase):
    def test_empty_build(self) -> None:
        d = CostDashboard()
        report = d.build()
        self.assertIsInstance(report, DashboardReport)
        self.assertEqual(report.total_cost, 0.0)
        self.assertEqual(report.daily_trend, [])

    def test_daily_aggregation(self) -> None:
        d = CostDashboard()
        d.add_records([
            {"date": "2026-01-01", "amount": 100, "service": "EC2", "environment": "prod"},
            {"date": "2026-01-01", "amount": 50, "service": "S3", "environment": "prod"},
            {"date": "2026-01-02", "amount": 200, "service": "EC2", "environment": "prod"},
        ])
        report = d.build()
        self.assertEqual(report.total_cost, 350.0)
        self.assertEqual(len(report.daily_trend), 2)
        self.assertEqual(report.daily_trend[0].label, "2026-01-01")
        self.assertEqual(report.daily_trend[0].amount, 150.0)

    def test_monthly_aggregation(self) -> None:
        d = CostDashboard()
        d.add_records([
            {"date": "2026-01-01", "amount": 100, "service": "EC2", "environment": "prod"},
            {"date": "2026-01-15", "amount": 100, "service": "EC2", "environment": "prod"},
            {"date": "2026-02-01", "amount": 200, "service": "EC2", "environment": "prod"},
        ])
        report = d.build()
        self.assertEqual(len(report.monthly_trend), 2)
        self.assertEqual(report.monthly_trend[0].label, "2026-01")
        self.assertEqual(report.monthly_trend[0].amount, 200.0)

    def test_environment_breakdown(self) -> None:
        d = CostDashboard()
        d.add_records([
            {"date": "2026-01-01", "amount": 100, "service": "EC2", "environment": "prod"},
            {"date": "2026-01-01", "amount": 50, "service": "EC2", "environment": "staging"},
            {"date": "2026-01-01", "amount": 30, "service": "S3", "environment": "prod"},
        ])
        report = d.build()
        self.assertEqual(len(report.environments), 2)
        prod = [e for e in report.environments if e.environment == "prod"][0]
        self.assertEqual(prod.total_cost, 130.0)
        self.assertEqual(prod.service_breakdown["EC2"], 100.0)

    def test_tag_grouping(self) -> None:
        d = CostDashboard()
        d.add_records([
            {"date": "2026-01-01", "amount": 100, "service": "EC2", "environment": "prod",
             "tags": {"team": "backend"}},
            {"date": "2026-01-02", "amount": 50, "service": "S3", "environment": "prod",
             "tags": {"team": "backend"}},
            {"date": "2026-01-03", "amount": 80, "service": "EC2", "environment": "prod",
             "tags": {"team": "frontend"}},
        ])
        report = d.build()
        self.assertEqual(len(report.tag_groups), 2)
        backend = [t for t in report.tag_groups if t.tag_value == "backend"][0]
        self.assertEqual(backend.total_cost, 150.0)

    def test_anomaly_detection(self) -> None:
        d = CostDashboard(anomaly_threshold=2.0)
        records = [
            {"date": f"2026-01-{i:02d}", "amount": 100.0, "service": "EC2", "environment": "prod"}
            for i in range(1, 10)
        ]
        # Spike on day 10
        records.append(
            {"date": "2026-01-10", "amount": 1000.0, "service": "EC2", "environment": "prod"}
        )
        d.add_records(records)
        report = d.build()
        self.assertGreater(len(report.anomalies), 0)
        spike = report.anomalies[0]
        self.assertIsInstance(spike, Anomaly)
        self.assertEqual(spike.amount, 1000.0)
        self.assertGreater(spike.deviation_pct, 0)

    def test_no_anomaly_stable_data(self) -> None:
        d = CostDashboard()
        records = [
            {"date": f"2026-01-{i:02d}", "amount": 100.0, "service": "EC2", "environment": "prod"}
            for i in range(1, 10)
        ]
        d.add_records(records)
        report = d.build()
        self.assertEqual(len(report.anomalies), 0)

    def test_custom_currency(self) -> None:
        d = CostDashboard(currency="GBP")
        d.add_records([{"date": "2026-01-01", "amount": 10, "service": "S3", "environment": "dev"}])
        report = d.build()
        self.assertEqual(report.currency, "GBP")

    def test_weekly_trend(self) -> None:
        d = CostDashboard()
        d.add_records([
            {"date": "2026-01-01", "amount": 50, "service": "EC2", "environment": "prod"},
            {"date": "2026-01-08", "amount": 75, "service": "EC2", "environment": "prod"},
        ])
        report = d.build()
        self.assertGreater(len(report.weekly_trend), 0)

    def test_immutable_records(self) -> None:
        d = CostDashboard()
        original = [{"date": "2026-01-01", "amount": 10, "service": "S3", "environment": "dev"}]
        d.add_records(original)
        d.add_records([{"date": "2026-01-02", "amount": 20, "service": "S3", "environment": "dev"}])
        self.assertEqual(len(original), 1)


if __name__ == "__main__":
    unittest.main()
