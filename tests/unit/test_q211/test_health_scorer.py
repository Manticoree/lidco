"""Tests for HealthScorer, HealthDimension, HealthReport."""
from __future__ import annotations

import unittest

from lidco.project_analytics.health_scorer import (
    HealthDimension,
    HealthReport,
    HealthScorer,
)


class TestHealthDimension(unittest.TestCase):
    def test_frozen(self):
        dim = HealthDimension(name="test", score=80.0)
        with self.assertRaises(AttributeError):
            dim.name = "x"  # type: ignore[misc]

    def test_defaults(self):
        dim = HealthDimension(name="a", score=50.0)
        self.assertEqual(dim.weight, 1.0)
        self.assertEqual(dim.detail, "")


class TestHealthReport(unittest.TestCase):
    def test_frozen(self):
        report = HealthReport(overall_score=75.0)
        with self.assertRaises(AttributeError):
            report.overall_score = 0.0  # type: ignore[misc]

    def test_defaults(self):
        report = HealthReport(overall_score=50.0)
        self.assertEqual(report.dimensions, ())
        self.assertEqual(report.project_path, "")


class TestHealthScorer(unittest.TestCase):
    def test_empty_compute(self):
        scorer = HealthScorer()
        report = scorer.compute()
        self.assertEqual(report.overall_score, 0.0)
        self.assertEqual(report.dimensions, ())

    def test_single_dimension(self):
        scorer = HealthScorer()
        scorer.add_dimension("quality", 80.0)
        report = scorer.compute()
        self.assertAlmostEqual(report.overall_score, 80.0, places=1)

    def test_weighted_average(self):
        scorer = HealthScorer()
        scorer.add_dimension("a", 100.0, weight=2.0)
        scorer.add_dimension("b", 50.0, weight=1.0)
        report = scorer.compute()
        # (100*2 + 50*1) / 3 = 83.33
        self.assertAlmostEqual(report.overall_score, 83.33, places=1)

    def test_grade_a(self):
        scorer = HealthScorer()
        scorer.add_dimension("x", 95.0)
        self.assertEqual(scorer.grade(), "A")

    def test_grade_f(self):
        scorer = HealthScorer()
        scorer.add_dimension("x", 30.0)
        self.assertEqual(scorer.grade(), "F")

    def test_trend_improving(self):
        reports = [
            HealthReport(overall_score=50.0),
            HealthReport(overall_score=60.0),
        ]
        self.assertEqual(HealthScorer.trend(reports), "improving")

    def test_trend_declining(self):
        reports = [
            HealthReport(overall_score=80.0),
            HealthReport(overall_score=70.0),
        ]
        self.assertEqual(HealthScorer.trend(reports), "declining")

    def test_trend_stable(self):
        reports = [
            HealthReport(overall_score=80.0),
            HealthReport(overall_score=81.0),
        ]
        self.assertEqual(HealthScorer.trend(reports), "stable")

    def test_set_project_and_reset(self):
        scorer = HealthScorer()
        scorer.set_project("/foo")
        scorer.add_dimension("a", 50.0)
        report = scorer.compute()
        self.assertEqual(report.project_path, "/foo")
        scorer.reset()
        report2 = scorer.compute()
        self.assertEqual(report2.overall_score, 0.0)
        self.assertEqual(report2.project_path, "")

    def test_score_clamped(self):
        scorer = HealthScorer()
        scorer.add_dimension("over", 200.0)
        scorer.add_dimension("under", -50.0)
        report = scorer.compute()
        self.assertGreaterEqual(report.overall_score, 0.0)
        self.assertLessEqual(report.overall_score, 100.0)
