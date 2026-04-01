"""Tests for economics.cost_projector — Projection, CostProjector."""
from __future__ import annotations

import unittest

from lidco.economics.cost_hook import CostRecord
from lidco.economics.cost_projector import CostProjector, Projection


class TestProjection(unittest.TestCase):
    def test_frozen(self):
        p = Projection(estimated_total=1.0, remaining=0.5, confidence=0.8, anomaly=False)
        with self.assertRaises(AttributeError):
            p.estimated_total = 2.0  # type: ignore[misc]

    def test_fields(self):
        p = Projection(1.5, 0.5, 0.9, True)
        self.assertAlmostEqual(p.estimated_total, 1.5)
        self.assertAlmostEqual(p.remaining, 0.5)
        self.assertAlmostEqual(p.confidence, 0.9)
        self.assertTrue(p.anomaly)

    def test_equality(self):
        a = Projection(1.0, 0.5, 0.8, False)
        b = Projection(1.0, 0.5, 0.8, False)
        self.assertEqual(a, b)


class TestCostProjector(unittest.TestCase):
    def _record(self, cost):
        return CostRecord("m", 100, 100, cost, "t")

    def test_project_empty(self):
        proj = CostProjector()
        result = proj.project(10)
        self.assertAlmostEqual(result.estimated_total, 0.0)
        self.assertAlmostEqual(result.confidence, 0.0)

    def test_project_basic(self):
        records = tuple(self._record(0.01) for _ in range(5))
        proj = CostProjector(records)
        result = proj.project(5)
        # Current: 5 * 0.01 = 0.05, avg = 0.01, remaining = 5 * 0.01 = 0.05
        self.assertAlmostEqual(result.estimated_total, 0.10)
        self.assertAlmostEqual(result.remaining, 0.05)

    def test_project_confidence_grows(self):
        r2 = tuple(self._record(0.01) for _ in range(2))
        r10 = tuple(self._record(0.01) for _ in range(10))
        p2 = CostProjector(r2).project(5)
        p10 = CostProjector(r10).project(5)
        self.assertLess(p2.confidence, p10.confidence)

    def test_detect_anomaly_normal(self):
        records = tuple(self._record(0.01) for _ in range(5))
        proj = CostProjector(records)
        normal = self._record(0.02)
        self.assertFalse(proj.detect_anomaly(normal))

    def test_detect_anomaly_high(self):
        records = tuple(self._record(0.01) for _ in range(5))
        proj = CostProjector(records)
        spike = self._record(0.05)
        self.assertTrue(proj.detect_anomaly(spike))

    def test_detect_anomaly_empty(self):
        proj = CostProjector()
        self.assertFalse(proj.detect_anomaly(self._record(0.01)))

    def test_trend_stable(self):
        records = tuple(self._record(0.01) for _ in range(10))
        proj = CostProjector(records)
        self.assertEqual(proj.trend(), "stable")

    def test_trend_increasing(self):
        low = tuple(self._record(0.01) for _ in range(5))
        high = tuple(self._record(0.10) for _ in range(5))
        proj = CostProjector(low + high)
        self.assertEqual(proj.trend(), "increasing")

    def test_trend_decreasing(self):
        high = tuple(self._record(0.10) for _ in range(5))
        low = tuple(self._record(0.01) for _ in range(5))
        proj = CostProjector(high + low)
        self.assertEqual(proj.trend(), "decreasing")

    def test_trend_single_record(self):
        proj = CostProjector((self._record(0.01),))
        self.assertEqual(proj.trend(), "stable")

    def test_project_zero_remaining(self):
        records = (self._record(0.05),)
        proj = CostProjector(records)
        result = proj.project(0)
        self.assertAlmostEqual(result.remaining, 0.0)
        self.assertAlmostEqual(result.estimated_total, 0.05)

    def test_detect_anomaly_zero_avg(self):
        records = tuple(self._record(0.0) for _ in range(5))
        proj = CostProjector(records)
        self.assertTrue(proj.detect_anomaly(self._record(0.01)))

    def test_project_returns_projection(self):
        proj = CostProjector((self._record(0.01),))
        self.assertIsInstance(proj.project(5), Projection)

    def test_confidence_capped_at_one(self):
        records = tuple(self._record(0.01) for _ in range(100))
        proj = CostProjector(records)
        result = proj.project(5)
        self.assertLessEqual(result.confidence, 1.0)

    def test_detect_anomaly_exactly_3x(self):
        records = tuple(self._record(0.01) for _ in range(5))
        proj = CostProjector(records)
        # Exactly 3x should not be anomaly (>3x is anomaly)
        self.assertFalse(proj.detect_anomaly(self._record(0.03)))

    def test_project_large_remaining(self):
        records = (self._record(0.10),)
        proj = CostProjector(records)
        result = proj.project(1000)
        self.assertAlmostEqual(result.remaining, 100.0)


class TestCostProjectorAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.economics import cost_projector

        self.assertIn("Projection", cost_projector.__all__)
        self.assertIn("CostProjector", cost_projector.__all__)


if __name__ == "__main__":
    unittest.main()
