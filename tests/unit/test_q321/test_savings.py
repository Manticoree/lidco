"""Tests for lidco.cloudcost.savings — SavingsFinder."""

from __future__ import annotations

import unittest

from lidco.cloudcost.savings import SavingsFinder, SavingsOpportunity, SavingsReport


class TestSavingsOpportunity(unittest.TestCase):
    def test_frozen(self) -> None:
        o = SavingsOpportunity(
            category="reserved",
            description="test",
            current_cost=1200.0,
            projected_cost=720.0,
            annual_savings=480.0,
            roi_pct=40.0,
            risk="low",
        )
        self.assertEqual(o.category, "reserved")
        with self.assertRaises(AttributeError):
            o.category = "spot"  # type: ignore[misc]

    def test_default_resource_ids(self) -> None:
        o = SavingsOpportunity(
            category="spot", description="d", current_cost=0,
            projected_cost=0, annual_savings=0, roi_pct=0, risk="low",
        )
        self.assertEqual(o.resource_ids, [])


class TestSavingsFinder(unittest.TestCase):
    def test_empty_report(self) -> None:
        finder = SavingsFinder()
        report = finder.find()
        self.assertIsInstance(report, SavingsReport)
        self.assertEqual(report.total_annual_savings, 0.0)
        self.assertEqual(report.opportunities, [])

    def test_reserved_instance_opportunity(self) -> None:
        finder = SavingsFinder()
        finder.add_resources([
            {"resource_id": "i-1", "service": "EC2", "monthly_cost": 100, "on_demand": True},
        ])
        report = finder.find()
        reserved = [o for o in report.opportunities if o.category == "reserved"]
        self.assertEqual(len(reserved), 1)
        self.assertEqual(reserved[0].roi_pct, 40.0)
        self.assertAlmostEqual(reserved[0].annual_savings, 1200 * 0.4, places=1)

    def test_spot_instance_opportunity(self) -> None:
        finder = SavingsFinder()
        finder.add_resources([
            {"resource_id": "i-2", "service": "EC2", "monthly_cost": 100},
        ])
        finder.add_usage_patterns([
            {"resource_id": "i-2", "interruptible": True},
        ])
        report = finder.find()
        spot = [o for o in report.opportunities if o.category == "spot"]
        self.assertEqual(len(spot), 1)
        self.assertEqual(spot[0].risk, "high")

    def test_autoscaling_opportunity(self) -> None:
        finder = SavingsFinder()
        finder.add_resources([
            {"resource_id": "i-3", "service": "EC2", "monthly_cost": 200, "scalable": True},
        ])
        finder.add_usage_patterns([
            {"resource_id": "i-3", "off_hours_util": 5},
        ])
        report = finder.find()
        auto = [o for o in report.opportunities if o.category == "auto-scaling"]
        self.assertEqual(len(auto), 1)
        self.assertEqual(auto[0].risk, "medium")

    def test_rightsizing_opportunity(self) -> None:
        finder = SavingsFinder()
        finder.add_resources([
            {"resource_id": "i-4", "service": "EC2", "monthly_cost": 300, "cpu_util": 10},
        ])
        report = finder.find()
        rs = [o for o in report.opportunities if o.category == "rightsizing"]
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0].roi_pct, 50.0)

    def test_no_rightsizing_high_cpu(self) -> None:
        finder = SavingsFinder()
        finder.add_resources([
            {"resource_id": "i-5", "service": "EC2", "monthly_cost": 300, "cpu_util": 80},
        ])
        report = finder.find()
        rs = [o for o in report.opportunities if o.category == "rightsizing"]
        self.assertEqual(len(rs), 0)

    def test_summary_by_category(self) -> None:
        finder = SavingsFinder()
        finder.add_resources([
            {"resource_id": "i-a", "service": "EC2", "monthly_cost": 100, "on_demand": True},
            {"resource_id": "i-b", "service": "EC2", "monthly_cost": 200, "cpu_util": 5},
        ])
        report = finder.find()
        self.assertIn("reserved", report.summary_by_category)
        self.assertIn("rightsizing", report.summary_by_category)

    def test_multiple_opportunities_same_resource(self) -> None:
        finder = SavingsFinder()
        finder.add_resources([
            {"resource_id": "i-x", "service": "EC2", "monthly_cost": 100,
             "on_demand": True, "cpu_util": 10, "scalable": True},
        ])
        finder.add_usage_patterns([
            {"resource_id": "i-x", "interruptible": True, "off_hours_util": 5},
        ])
        report = finder.find()
        categories = {o.category for o in report.opportunities}
        # Should have reserved + spot + autoscaling + rightsizing
        self.assertTrue(categories.issuperset({"reserved", "spot", "auto-scaling", "rightsizing"}))

    def test_total_calculations(self) -> None:
        finder = SavingsFinder()
        finder.add_resources([
            {"resource_id": "i-1", "service": "EC2", "monthly_cost": 100, "on_demand": True},
        ])
        report = finder.find()
        self.assertGreater(report.total_current_annual, 0)
        self.assertGreater(report.total_projected_annual, 0)
        self.assertEqual(
            report.total_annual_savings,
            round(report.total_current_annual - report.total_projected_annual, 2),
        )

    def test_immutable_resources(self) -> None:
        finder = SavingsFinder()
        original = [{"resource_id": "i-1", "service": "S3", "monthly_cost": 10}]
        finder.add_resources(original)
        finder.add_resources([{"resource_id": "i-2", "service": "S3", "monthly_cost": 20}])
        self.assertEqual(len(original), 1)


if __name__ == "__main__":
    unittest.main()
