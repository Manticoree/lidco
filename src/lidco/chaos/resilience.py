"""
Resilience Score — score system resilience based on chaos experiment results.

Evaluates test coverage of failure modes, recovery speed, and graceful degradation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lidco.chaos.experiments import ExperimentResult, ExperimentStatus, ExperimentType
from lidco.chaos.monitor import ChaosMonitor, RecoveryReport


class ResilienceGrade:
    """Grade thresholds for resilience scores."""

    EXCELLENT = "A"
    GOOD = "B"
    FAIR = "C"
    POOR = "D"
    CRITICAL = "F"

    @staticmethod
    def from_score(score: float) -> str:
        if score >= 90:
            return ResilienceGrade.EXCELLENT
        if score >= 75:
            return ResilienceGrade.GOOD
        if score >= 60:
            return ResilienceGrade.FAIR
        if score >= 40:
            return ResilienceGrade.POOR
        return ResilienceGrade.CRITICAL


@dataclass(frozen=True)
class DimensionScore:
    """Score for a single resilience dimension."""

    name: str
    score: float
    max_score: float
    details: str = ""

    @property
    def normalized(self) -> float:
        if self.max_score <= 0:
            return 0.0
        return min(self.score / self.max_score, 1.0)


@dataclass(frozen=True)
class ResilienceReport:
    """Overall resilience report."""

    overall_score: float
    grade: str
    dimensions: list[DimensionScore] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    experiment_count: int = 0
    failure_modes_tested: int = 0
    avg_recovery_seconds: float = 0.0


class ResilienceScorer:
    """Score system resilience from chaos experiment results."""

    ALL_FAILURE_MODES = {
        ExperimentType.NETWORK_DELAY,
        ExperimentType.DISK_FULL,
        ExperimentType.SERVICE_DOWN,
        ExperimentType.CPU_SPIKE,
        ExperimentType.MEMORY_PRESSURE,
    }

    def __init__(
        self,
        *,
        recovery_target_seconds: float = 30.0,
        error_tolerance: float = 0.1,
    ) -> None:
        self._recovery_target = recovery_target_seconds
        self._error_tolerance = error_tolerance

    def score(
        self,
        results: list[ExperimentResult],
        *,
        monitor: ChaosMonitor | None = None,
        recovery_reports: list[RecoveryReport] | None = None,
    ) -> ResilienceReport:
        """Compute a resilience score from experiment results."""
        if not results:
            return ResilienceReport(
                overall_score=0.0,
                grade=ResilienceGrade.CRITICAL,
                recommendations=["No chaos experiments have been run yet."],
            )

        dimensions: list[DimensionScore] = []
        recommendations: list[str] = []

        # 1. Coverage — how many failure modes tested
        coverage = self._score_coverage(results)
        dimensions.append(coverage)

        # 2. Success rate — experiments that completed without system failure
        success = self._score_success_rate(results)
        dimensions.append(success)

        # 3. Recovery speed
        recoveries = recovery_reports or (
            monitor.recovery_reports if monitor else []
        )
        recovery = self._score_recovery(recoveries)
        dimensions.append(recovery)

        # 4. Graceful degradation — low error counts during experiments
        degradation = self._score_degradation(results)
        dimensions.append(degradation)

        # Compute overall as weighted average
        weights = [25.0, 30.0, 25.0, 20.0]
        total_weighted = sum(
            d.normalized * w for d, w in zip(dimensions, weights)
        )
        overall = total_weighted / sum(weights) * 100

        # Recommendations
        if coverage.normalized < 0.6:
            recommendations.append(
                "Increase failure mode coverage — test more experiment types."
            )
        if success.normalized < 0.8:
            recommendations.append(
                "Improve system stability — too many experiments led to failures."
            )
        if recovery.normalized < 0.7:
            recommendations.append(
                f"Improve recovery speed — target under {self._recovery_target}s."
            )
        if degradation.normalized < 0.7:
            recommendations.append(
                "Improve graceful degradation — reduce error counts during chaos."
            )

        tested_types = {r.experiment_type for r in results}
        avg_recovery = 0.0
        if recoveries:
            avg_recovery = sum(
                r.recovery_time_seconds for r in recoveries
            ) / len(recoveries)

        return ResilienceReport(
            overall_score=round(overall, 1),
            grade=ResilienceGrade.from_score(overall),
            dimensions=dimensions,
            recommendations=recommendations,
            experiment_count=len(results),
            failure_modes_tested=len(tested_types),
            avg_recovery_seconds=round(avg_recovery, 2),
        )

    def _score_coverage(self, results: list[ExperimentResult]) -> DimensionScore:
        tested = {r.experiment_type for r in results}
        covered = len(tested & self.ALL_FAILURE_MODES)
        total = len(self.ALL_FAILURE_MODES)
        return DimensionScore(
            name="Failure Mode Coverage",
            score=float(covered),
            max_score=float(total),
            details=f"{covered}/{total} failure modes tested",
        )

    def _score_success_rate(
        self, results: list[ExperimentResult]
    ) -> DimensionScore:
        completed = [r for r in results if r.status == ExperimentStatus.COMPLETED]
        return DimensionScore(
            name="Experiment Success Rate",
            score=float(len(completed)),
            max_score=float(len(results)),
            details=f"{len(completed)}/{len(results)} completed successfully",
        )

    def _score_recovery(
        self, recoveries: list[RecoveryReport]
    ) -> DimensionScore:
        if not recoveries:
            return DimensionScore(
                name="Recovery Speed",
                score=0.0,
                max_score=1.0,
                details="No recovery data available",
            )
        fast = [
            r
            for r in recoveries
            if r.recovery_time_seconds <= self._recovery_target
        ]
        return DimensionScore(
            name="Recovery Speed",
            score=float(len(fast)),
            max_score=float(len(recoveries)),
            details=f"{len(fast)}/{len(recoveries)} within {self._recovery_target}s target",
        )

    def _score_degradation(
        self, results: list[ExperimentResult]
    ) -> DimensionScore:
        if not results:
            return DimensionScore(
                name="Graceful Degradation",
                score=0.0,
                max_score=1.0,
                details="No experiment data",
            )
        graceful = [r for r in results if r.errors_observed == 0]
        return DimensionScore(
            name="Graceful Degradation",
            score=float(len(graceful)),
            max_score=float(len(results)),
            details=f"{len(graceful)}/{len(results)} with zero errors",
        )
