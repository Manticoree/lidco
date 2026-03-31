"""Tests for Q148 WorkspaceHealth."""
from __future__ import annotations

import unittest
from lidco.maintenance.workspace_health import WorkspaceHealth, HealthMetric, HealthReport


class TestHealthMetric(unittest.TestCase):
    def test_fields(self):
        m = HealthMetric(name="test", score=0.85, weight=1.0, message="good")
        self.assertEqual(m.name, "test")
        self.assertAlmostEqual(m.score, 0.85)
        self.assertEqual(m.weight, 1.0)
        self.assertEqual(m.message, "good")


class TestHealthReport(unittest.TestCase):
    def test_defaults(self):
        r = HealthReport(overall_score=0.5)
        self.assertEqual(r.grade, "F")
        self.assertEqual(r.metrics, [])
        self.assertEqual(r.recommendations, [])

    def test_independent_lists(self):
        r1 = HealthReport(overall_score=0.5)
        r2 = HealthReport(overall_score=0.5)
        r1.metrics.append(HealthMetric("x", 0.5, 1.0, ""))
        self.assertEqual(len(r2.metrics), 0)


class TestGrade(unittest.TestCase):
    def test_grade_a(self):
        self.assertEqual(WorkspaceHealth.grade(0.95), "A")
        self.assertEqual(WorkspaceHealth.grade(0.9), "A")

    def test_grade_b(self):
        self.assertEqual(WorkspaceHealth.grade(0.85), "B")
        self.assertEqual(WorkspaceHealth.grade(0.8), "B")

    def test_grade_c(self):
        self.assertEqual(WorkspaceHealth.grade(0.75), "C")
        self.assertEqual(WorkspaceHealth.grade(0.7), "C")

    def test_grade_d(self):
        self.assertEqual(WorkspaceHealth.grade(0.65), "D")
        self.assertEqual(WorkspaceHealth.grade(0.6), "D")

    def test_grade_f(self):
        self.assertEqual(WorkspaceHealth.grade(0.5), "F")
        self.assertEqual(WorkspaceHealth.grade(0.0), "F")

    def test_grade_boundary(self):
        self.assertEqual(WorkspaceHealth.grade(0.89999), "B")


class TestAddMetric(unittest.TestCase):
    def test_add_single(self):
        wh = WorkspaceHealth()
        wh.add_metric("test", lambda: (1.0, "ok"))
        report = wh.evaluate()
        self.assertEqual(len(report.metrics), 1)

    def test_add_multiple(self):
        wh = WorkspaceHealth()
        wh.add_metric("a", lambda: (0.9, "good"))
        wh.add_metric("b", lambda: (0.8, "fine"))
        report = wh.evaluate()
        self.assertEqual(len(report.metrics), 2)


class TestEvaluate(unittest.TestCase):
    def test_perfect_score(self):
        wh = WorkspaceHealth()
        wh.add_metric("a", lambda: (1.0, "perfect"))
        report = wh.evaluate()
        self.assertAlmostEqual(report.overall_score, 1.0)
        self.assertEqual(report.grade, "A")

    def test_zero_score(self):
        wh = WorkspaceHealth()
        wh.add_metric("a", lambda: (0.0, "bad"))
        report = wh.evaluate()
        self.assertAlmostEqual(report.overall_score, 0.0)
        self.assertEqual(report.grade, "F")

    def test_weighted_average(self):
        wh = WorkspaceHealth()
        wh.add_metric("a", lambda: (1.0, "ok"), weight=3.0)
        wh.add_metric("b", lambda: (0.0, "bad"), weight=1.0)
        report = wh.evaluate()
        self.assertAlmostEqual(report.overall_score, 0.75)

    def test_no_metrics(self):
        wh = WorkspaceHealth()
        report = wh.evaluate()
        self.assertAlmostEqual(report.overall_score, 0.0)
        self.assertEqual(report.grade, "F")

    def test_recommendations_for_low_scores(self):
        wh = WorkspaceHealth()
        wh.add_metric("bad", lambda: (0.3, "needs work"))
        report = wh.evaluate()
        self.assertTrue(len(report.recommendations) > 0)
        self.assertIn("bad", report.recommendations[0])

    def test_no_recommendations_for_high_scores(self):
        wh = WorkspaceHealth()
        wh.add_metric("good", lambda: (0.9, "great"))
        report = wh.evaluate()
        self.assertEqual(len(report.recommendations), 0)

    def test_score_clamped_above_1(self):
        wh = WorkspaceHealth()
        wh.add_metric("over", lambda: (1.5, "too high"))
        report = wh.evaluate()
        self.assertLessEqual(report.metrics[0].score, 1.0)

    def test_score_clamped_below_0(self):
        wh = WorkspaceHealth()
        wh.add_metric("under", lambda: (-0.5, "too low"))
        report = wh.evaluate()
        self.assertGreaterEqual(report.metrics[0].score, 0.0)

    def test_exception_in_check(self):
        def broken():
            raise ValueError("boom")
        wh = WorkspaceHealth()
        wh.add_metric("broken", broken)
        report = wh.evaluate()
        self.assertAlmostEqual(report.metrics[0].score, 0.0)
        self.assertIn("boom", report.metrics[0].message)

    def test_custom_weight(self):
        wh = WorkspaceHealth()
        wh.add_metric("a", lambda: (1.0, "ok"), weight=2.0)
        report = wh.evaluate()
        self.assertEqual(report.metrics[0].weight, 2.0)


class TestFormatReport(unittest.TestCase):
    def test_format_includes_grade(self):
        report = HealthReport(overall_score=0.85, grade="B", metrics=[], recommendations=[])
        s = WorkspaceHealth.format_report(report)
        self.assertIn("B", s)

    def test_format_includes_metrics(self):
        report = HealthReport(
            overall_score=0.9,
            grade="A",
            metrics=[HealthMetric("test", 0.9, 1.0, "fine")],
            recommendations=[],
        )
        s = WorkspaceHealth.format_report(report)
        self.assertIn("test", s)
        self.assertIn("fine", s)

    def test_format_includes_recommendations(self):
        report = HealthReport(
            overall_score=0.5,
            grade="F",
            metrics=[],
            recommendations=["Fix X"],
        )
        s = WorkspaceHealth.format_report(report)
        self.assertIn("Fix X", s)

    def test_format_empty_report(self):
        report = HealthReport(overall_score=0.0, grade="F")
        s = WorkspaceHealth.format_report(report)
        self.assertIn("F", s)


if __name__ == "__main__":
    unittest.main()
