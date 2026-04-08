"""Tests for lidco.chaos.resilience."""

from __future__ import annotations

import unittest

from lidco.chaos.experiments import ExperimentResult, ExperimentStatus, ExperimentType
from lidco.chaos.monitor import ChaosMonitor, RecoveryReport
from lidco.chaos.resilience import (
    DimensionScore,
    ResilienceGrade,
    ResilienceReport,
    ResilienceScorer,
)


def _make_result(
    exp_type: ExperimentType = ExperimentType.NETWORK_DELAY,
    status: ExperimentStatus = ExperimentStatus.COMPLETED,
    errors: int = 0,
) -> ExperimentResult:
    return ExperimentResult(
        experiment_id="test-id",
        experiment_type=exp_type,
        status=status,
        started_at=100.0,
        ended_at=130.0,
        errors_observed=errors,
    )


def _make_recovery(
    exp_id: str = "test",
    recovery_time: float = 5.0,
    full: bool = True,
) -> RecoveryReport:
    return RecoveryReport(
        experiment_id=exp_id,
        failure_detected_at=100.0,
        recovery_detected_at=100.0 + recovery_time,
        recovery_time_seconds=recovery_time,
        full_recovery=full,
    )


class TestResilienceGrade(unittest.TestCase):
    def test_excellent(self) -> None:
        self.assertEqual(ResilienceGrade.from_score(95), "A")

    def test_good(self) -> None:
        self.assertEqual(ResilienceGrade.from_score(80), "B")

    def test_fair(self) -> None:
        self.assertEqual(ResilienceGrade.from_score(65), "C")

    def test_poor(self) -> None:
        self.assertEqual(ResilienceGrade.from_score(45), "D")

    def test_critical(self) -> None:
        self.assertEqual(ResilienceGrade.from_score(30), "F")

    def test_boundary_90(self) -> None:
        self.assertEqual(ResilienceGrade.from_score(90), "A")

    def test_boundary_75(self) -> None:
        self.assertEqual(ResilienceGrade.from_score(75), "B")

    def test_boundary_60(self) -> None:
        self.assertEqual(ResilienceGrade.from_score(60), "C")

    def test_boundary_40(self) -> None:
        self.assertEqual(ResilienceGrade.from_score(40), "D")


class TestDimensionScore(unittest.TestCase):
    def test_normalized(self) -> None:
        d = DimensionScore(name="test", score=3.0, max_score=5.0)
        self.assertAlmostEqual(d.normalized, 0.6)

    def test_normalized_zero_max(self) -> None:
        d = DimensionScore(name="test", score=0.0, max_score=0.0)
        self.assertEqual(d.normalized, 0.0)

    def test_normalized_capped(self) -> None:
        d = DimensionScore(name="test", score=10.0, max_score=5.0)
        self.assertEqual(d.normalized, 1.0)


class TestResilienceScorer(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = ResilienceScorer(
            recovery_target_seconds=30.0,
            error_tolerance=0.1,
        )

    def test_no_results(self) -> None:
        report = self.scorer.score([])
        self.assertEqual(report.overall_score, 0.0)
        self.assertEqual(report.grade, "F")
        self.assertEqual(len(report.recommendations), 1)

    def test_single_completed(self) -> None:
        results = [_make_result()]
        report = self.scorer.score(results)
        self.assertGreater(report.overall_score, 0)
        self.assertEqual(report.experiment_count, 1)
        self.assertEqual(report.failure_modes_tested, 1)

    def test_multiple_types(self) -> None:
        results = [
            _make_result(ExperimentType.NETWORK_DELAY),
            _make_result(ExperimentType.DISK_FULL),
            _make_result(ExperimentType.SERVICE_DOWN),
            _make_result(ExperimentType.CPU_SPIKE),
            _make_result(ExperimentType.MEMORY_PRESSURE),
        ]
        report = self.scorer.score(results)
        self.assertEqual(report.failure_modes_tested, 5)
        # Full coverage + all completed + zero errors = high score
        self.assertGreater(report.overall_score, 50)

    def test_failed_experiments_lower_score(self) -> None:
        good = [_make_result()]
        bad = [_make_result(status=ExperimentStatus.FAILED)]
        report_good = self.scorer.score(good)
        report_bad = self.scorer.score(bad)
        self.assertGreater(report_good.overall_score, report_bad.overall_score)

    def test_with_recovery_reports(self) -> None:
        results = [_make_result()]
        recoveries = [_make_recovery(recovery_time=5.0)]
        report = self.scorer.score(results, recovery_reports=recoveries)
        self.assertGreater(report.avg_recovery_seconds, 0)

    def test_with_monitor(self) -> None:
        monitor = ChaosMonitor()
        import time
        now = time.time()
        monitor.record_recovery("e1", failure_at=now - 10, recovery_at=now)
        results = [_make_result()]
        report = self.scorer.score(results, monitor=monitor)
        self.assertEqual(report.experiment_count, 1)

    def test_slow_recovery_lowers_score(self) -> None:
        results = [_make_result()]
        fast = [_make_recovery(recovery_time=5.0)]
        slow = [_make_recovery(recovery_time=999.0)]
        report_fast = self.scorer.score(results, recovery_reports=fast)
        report_slow = self.scorer.score(results, recovery_reports=slow)
        self.assertGreaterEqual(
            report_fast.overall_score, report_slow.overall_score
        )

    def test_errors_lower_degradation_score(self) -> None:
        clean = [_make_result(errors=0)]
        dirty = [_make_result(errors=10)]
        report_clean = self.scorer.score(clean)
        report_dirty = self.scorer.score(dirty)
        self.assertGreater(
            report_clean.overall_score, report_dirty.overall_score
        )

    def test_recommendations_coverage(self) -> None:
        # Only 1 type tested out of 5 → coverage recommendation
        results = [_make_result()]
        report = self.scorer.score(results)
        recs = " ".join(report.recommendations)
        self.assertIn("coverage", recs.lower())

    def test_report_has_dimensions(self) -> None:
        results = [_make_result()]
        report = self.scorer.score(results)
        self.assertEqual(len(report.dimensions), 4)
        names = [d.name for d in report.dimensions]
        self.assertIn("Failure Mode Coverage", names)
        self.assertIn("Experiment Success Rate", names)
        self.assertIn("Recovery Speed", names)
        self.assertIn("Graceful Degradation", names)

    def test_grade_reflects_score(self) -> None:
        results = [
            _make_result(t)
            for t in [
                ExperimentType.NETWORK_DELAY,
                ExperimentType.DISK_FULL,
                ExperimentType.SERVICE_DOWN,
                ExperimentType.CPU_SPIKE,
                ExperimentType.MEMORY_PRESSURE,
            ]
        ]
        recoveries = [_make_recovery(recovery_time=2.0) for _ in range(5)]
        report = self.scorer.score(results, recovery_reports=recoveries)
        self.assertEqual(report.grade, ResilienceGrade.from_score(report.overall_score))


if __name__ == "__main__":
    unittest.main()
