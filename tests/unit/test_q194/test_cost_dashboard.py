"""Tests for economics.cost_dashboard — CostBreakdown, CostDashboard."""
from __future__ import annotations

import unittest

from lidco.economics.cost_dashboard import CostBreakdown, CostDashboard
from lidco.economics.cost_hook import CostRecord


class TestCostBreakdown(unittest.TestCase):
    def test_frozen(self):
        b = CostBreakdown(model="m", count=1, total_cost=0.01, avg_cost=0.01)
        with self.assertRaises(AttributeError):
            b.model = "x"  # type: ignore[misc]

    def test_fields(self):
        b = CostBreakdown("gpt-4", 3, 0.09, 0.03)
        self.assertEqual(b.model, "gpt-4")
        self.assertEqual(b.count, 3)
        self.assertAlmostEqual(b.total_cost, 0.09)
        self.assertAlmostEqual(b.avg_cost, 0.03)


class TestCostDashboard(unittest.TestCase):
    def _record(self, model, cost):
        return CostRecord(model=model, input_tokens=0, output_tokens=0, cost=cost, timestamp="t")

    def test_empty_dashboard(self):
        d = CostDashboard()
        self.assertAlmostEqual(d.session_total, 0.0)
        self.assertEqual(d.breakdown(), ())

    def test_add_record_returns_new(self):
        d1 = CostDashboard()
        d2 = d1.add_record(self._record("m", 0.01))
        self.assertIsNot(d1, d2)
        self.assertAlmostEqual(d1.session_total, 0.0)
        self.assertAlmostEqual(d2.session_total, 0.01)

    def test_breakdown_single_model(self):
        d = CostDashboard((self._record("gpt-4", 0.03), self._record("gpt-4", 0.06)))
        bd = d.breakdown()
        self.assertEqual(len(bd), 1)
        self.assertEqual(bd[0].model, "gpt-4")
        self.assertEqual(bd[0].count, 2)
        self.assertAlmostEqual(bd[0].total_cost, 0.09)
        self.assertAlmostEqual(bd[0].avg_cost, 0.045)

    def test_breakdown_multi_model_sorted(self):
        d = CostDashboard((
            self._record("cheap", 0.001),
            self._record("expensive", 0.1),
        ))
        bd = d.breakdown()
        self.assertEqual(bd[0].model, "expensive")
        self.assertEqual(bd[1].model, "cheap")

    def test_session_total(self):
        d = CostDashboard((
            self._record("a", 0.01),
            self._record("b", 0.02),
            self._record("a", 0.03),
        ))
        self.assertAlmostEqual(d.session_total, 0.06)

    def test_format_report_empty(self):
        d = CostDashboard()
        self.assertEqual(d.format_report(), "No cost records.")

    def test_format_report_with_data(self):
        d = CostDashboard((self._record("gpt-4", 0.05),))
        report = d.format_report()
        self.assertIn("Session total", report)
        self.assertIn("gpt-4", report)
        self.assertIn("1 calls", report)

    def test_add_multiple_records(self):
        d = CostDashboard()
        d = d.add_record(self._record("a", 0.01))
        d = d.add_record(self._record("b", 0.02))
        d = d.add_record(self._record("a", 0.03))
        self.assertEqual(len(d.breakdown()), 2)

    def test_breakdown_equality(self):
        a = CostBreakdown("m", 1, 0.01, 0.01)
        b = CostBreakdown("m", 1, 0.01, 0.01)
        self.assertEqual(a, b)

    def test_breakdown_different_not_equal(self):
        a = CostBreakdown("m1", 1, 0.01, 0.01)
        b = CostBreakdown("m2", 1, 0.01, 0.01)
        self.assertNotEqual(a, b)

    def test_immutability_chain(self):
        d1 = CostDashboard()
        d2 = d1.add_record(self._record("x", 1.0))
        d3 = d2.add_record(self._record("y", 2.0))
        self.assertAlmostEqual(d1.session_total, 0.0)
        self.assertAlmostEqual(d2.session_total, 1.0)
        self.assertAlmostEqual(d3.session_total, 3.0)

    def test_format_report_includes_avg(self):
        d = CostDashboard((self._record("m", 0.02), self._record("m", 0.04)))
        report = d.format_report()
        self.assertIn("avg", report)

    def test_breakdown_returns_tuple(self):
        d = CostDashboard((self._record("m", 0.01),))
        self.assertIsInstance(d.breakdown(), tuple)

    def test_init_with_records(self):
        recs = (self._record("a", 0.1), self._record("b", 0.2))
        d = CostDashboard(recs)
        self.assertAlmostEqual(d.session_total, 0.3)

    def test_zero_cost_records(self):
        d = CostDashboard((self._record("m", 0.0),))
        bd = d.breakdown()
        self.assertEqual(bd[0].count, 1)
        self.assertAlmostEqual(bd[0].avg_cost, 0.0)


class TestCostDashboardAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.economics import cost_dashboard

        self.assertIn("CostBreakdown", cost_dashboard.__all__)
        self.assertIn("CostDashboard", cost_dashboard.__all__)


if __name__ == "__main__":
    unittest.main()
