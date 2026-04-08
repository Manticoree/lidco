"""Tests for lidco.cloudcost.analyzer — CostAnalyzer."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from lidco.cloudcost.analyzer import (
    CostAnalyzer,
    CostBreakdown,
    RightSizingSuggestion,
    ServiceCost,
    UnusedResource,
)


class TestServiceCost(unittest.TestCase):
    def test_frozen_dataclass(self) -> None:
        sc = ServiceCost(service="EC2", cost=100.0, region="us-east-1")
        self.assertEqual(sc.service, "EC2")
        self.assertEqual(sc.cost, 100.0)
        self.assertEqual(sc.currency, "USD")
        self.assertEqual(sc.region, "us-east-1")
        with self.assertRaises(AttributeError):
            sc.cost = 200.0  # type: ignore[misc]

    def test_default_tags(self) -> None:
        sc = ServiceCost(service="S3", cost=50.0)
        self.assertEqual(sc.tags, {})


class TestRightSizingSuggestion(unittest.TestCase):
    def test_savings_property(self) -> None:
        rs = RightSizingSuggestion(
            resource_id="i-123",
            service="EC2",
            current_type="xlarge",
            suggested_type="large",
            current_cost=200.0,
            projected_cost=100.0,
        )
        self.assertEqual(rs.savings, 100.0)

    def test_savings_zero(self) -> None:
        rs = RightSizingSuggestion(
            resource_id="i-x",
            service="EC2",
            current_type="medium",
            suggested_type="medium",
            current_cost=50.0,
            projected_cost=50.0,
        )
        self.assertEqual(rs.savings, 0.0)


class TestCostAnalyzer(unittest.TestCase):
    def test_empty_analyze(self) -> None:
        analyzer = CostAnalyzer()
        result = analyzer.analyze()
        self.assertIsInstance(result, CostBreakdown)
        self.assertEqual(result.total_cost, 0.0)
        self.assertEqual(result.services, [])
        self.assertEqual(result.top_services, [])

    def test_add_records_and_analyze(self) -> None:
        analyzer = CostAnalyzer()
        analyzer.add_cost_records([
            {"service": "EC2", "cost": 100, "date": "2026-01-01"},
            {"service": "S3", "cost": 50, "date": "2026-01-02"},
            {"service": "EC2", "cost": 75, "date": "2026-01-03"},
        ])
        result = analyzer.analyze()
        self.assertEqual(result.total_cost, 225.0)
        self.assertEqual(len(result.services), 3)
        # Top service should be EC2
        self.assertEqual(result.top_services[0][0], "EC2")
        self.assertEqual(result.top_services[0][1], 175.0)

    def test_period_filter(self) -> None:
        analyzer = CostAnalyzer()
        analyzer.add_cost_records([
            {"service": "EC2", "cost": 100, "date": "2026-01-01"},
            {"service": "EC2", "cost": 200, "date": "2026-02-01"},
            {"service": "EC2", "cost": 300, "date": "2026-03-01"},
        ])
        result = analyzer.analyze(period_start="2026-02-01", period_end="2026-02-28")
        self.assertEqual(result.total_cost, 200.0)

    def test_unused_resource_low_cpu(self) -> None:
        analyzer = CostAnalyzer()
        analyzer.add_resources([
            {"resource_id": "i-1", "service": "EC2", "monthly_cost": 50, "cpu_util": 0.5},
        ])
        result = analyzer.analyze()
        self.assertEqual(len(result.unused_resources), 1)
        self.assertIn("CPU utilization", result.unused_resources[0].reason)

    def test_unused_resource_inactive(self) -> None:
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        analyzer = CostAnalyzer()
        analyzer.add_resources([
            {"resource_id": "i-2", "service": "EC2", "monthly_cost": 30, "cpu_util": 50, "last_active": old_date},
        ])
        result = analyzer.analyze()
        self.assertEqual(len(result.unused_resources), 1)
        self.assertIn("Inactive", result.unused_resources[0].reason)

    def test_no_unused_when_active(self) -> None:
        recent = datetime.now().isoformat()
        analyzer = CostAnalyzer()
        analyzer.add_resources([
            {"resource_id": "i-3", "service": "EC2", "monthly_cost": 30, "cpu_util": 80, "last_active": recent},
        ])
        result = analyzer.analyze()
        self.assertEqual(len(result.unused_resources), 0)

    def test_right_sizing_suggestions(self) -> None:
        analyzer = CostAnalyzer()
        analyzer.add_resources([
            {"resource_id": "i-4", "service": "EC2", "monthly_cost": 200, "cpu_util": 10, "type": "xlarge"},
        ])
        result = analyzer.analyze()
        self.assertEqual(len(result.right_sizing), 1)
        rs = result.right_sizing[0]
        self.assertEqual(rs.current_type, "xlarge")
        self.assertEqual(rs.suggested_type, "large")
        self.assertEqual(rs.projected_cost, 100.0)

    def test_no_rightsizing_high_cpu(self) -> None:
        analyzer = CostAnalyzer()
        analyzer.add_resources([
            {"resource_id": "i-5", "service": "EC2", "monthly_cost": 200, "cpu_util": 80, "type": "xlarge"},
        ])
        result = analyzer.analyze()
        self.assertEqual(len(result.right_sizing), 0)

    def test_currency_custom(self) -> None:
        analyzer = CostAnalyzer(currency="EUR")
        analyzer.add_cost_records([{"service": "S3", "cost": 10}])
        result = analyzer.analyze()
        self.assertEqual(result.currency, "EUR")

    def test_immutable_records(self) -> None:
        """add_cost_records should not mutate original list."""
        analyzer = CostAnalyzer()
        original = [{"service": "EC2", "cost": 100}]
        analyzer.add_cost_records(original)
        analyzer.add_cost_records([{"service": "S3", "cost": 50}])
        # Original list unmodified
        self.assertEqual(len(original), 1)


if __name__ == "__main__":
    unittest.main()
