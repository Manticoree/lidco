"""
Flaky test analyzer — identify root causes of flaky tests.

Categories: timing issues, order dependency, shared state, external deps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from lidco.flaky.detector import TestRun


class RootCause(Enum):
    """Root cause categories for flaky tests."""

    TIMING = "timing"
    ORDER_DEPENDENCY = "order_dependency"
    SHARED_STATE = "shared_state"
    EXTERNAL_DEPENDENCY = "external_dependency"
    RESOURCE_LEAK = "resource_leak"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CauseDetail:
    """Detail about a detected root cause."""

    cause: RootCause
    confidence: float  # 0.0 .. 1.0
    evidence: str = ""


@dataclass(frozen=True)
class AnalysisResult:
    """Analysis result for a single test."""

    test_name: str
    causes: list[CauseDetail] = field(default_factory=list)
    primary_cause: RootCause = RootCause.UNKNOWN
    recommendation: str = ""


@dataclass(frozen=True)
class AnalysisReport:
    """Full analysis report."""

    total_analyzed: int
    results: list[AnalysisResult] = field(default_factory=list)
    cause_counts: dict[str, int] = field(default_factory=dict)


class FlakyAnalyzer:
    """Analyze root causes of flaky tests.

    Parameters
    ----------
    timing_threshold_ms : float
        Duration standard deviation above this hints timing issues (default 500).
    min_runs : int
        Minimum runs needed for analysis (default 3).
    """

    def __init__(
        self,
        *,
        timing_threshold_ms: float = 500.0,
        min_runs: int = 3,
    ) -> None:
        self._timing_threshold_ms = timing_threshold_ms
        self._min_runs = max(1, min_runs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, runs: Sequence[TestRun]) -> AnalysisReport:
        """Analyze runs grouped by test name and return root-cause report."""
        grouped: dict[str, list[TestRun]] = {}
        for r in runs:
            grouped.setdefault(r.test_name, []).append(r)

        results: list[AnalysisResult] = []
        cause_totals: dict[str, int] = {}

        for name, test_runs in sorted(grouped.items()):
            if len(test_runs) < self._min_runs:
                continue
            result = self._analyze_test(name, test_runs)
            results.append(result)
            for c in result.causes:
                cause_totals[c.cause.value] = cause_totals.get(c.cause.value, 0) + 1

        return AnalysisReport(
            total_analyzed=len(results),
            results=results,
            cause_counts=cause_totals,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _analyze_test(self, name: str, runs: list[TestRun]) -> AnalysisResult:
        causes: list[CauseDetail] = []

        timing = self._check_timing(runs)
        if timing is not None:
            causes.append(timing)

        order = self._check_order_dependency(runs)
        if order is not None:
            causes.append(order)

        shared = self._check_shared_state(runs)
        if shared is not None:
            causes.append(shared)

        external = self._check_external_deps(runs)
        if external is not None:
            causes.append(external)

        if not causes:
            causes.append(CauseDetail(cause=RootCause.UNKNOWN, confidence=0.5))

        # Sort by confidence descending to pick primary
        causes.sort(key=lambda c: c.confidence, reverse=True)
        primary = causes[0].cause

        recommendation = self._recommend(primary)

        return AnalysisResult(
            test_name=name,
            causes=causes,
            primary_cause=primary,
            recommendation=recommendation,
        )

    def _check_timing(self, runs: list[TestRun]) -> CauseDetail | None:
        durations = [r.duration_ms for r in runs if r.duration_ms > 0]
        if len(durations) < 2:
            return None
        import statistics

        stdev = statistics.stdev(durations)
        if stdev > self._timing_threshold_ms:
            confidence = min(1.0, stdev / (self._timing_threshold_ms * 3))
            return CauseDetail(
                cause=RootCause.TIMING,
                confidence=confidence,
                evidence=f"Duration stdev={stdev:.1f}ms exceeds {self._timing_threshold_ms}ms threshold",
            )
        return None

    def _check_order_dependency(self, runs: list[TestRun]) -> CauseDetail | None:
        """Detect order dependency by checking if failures cluster at start."""
        if len(runs) < 4:
            return None
        half = len(runs) // 2
        first_half_fails = sum(1 for r in runs[:half] if not r.passed)
        second_half_fails = sum(1 for r in runs[half:] if not r.passed)
        total_fails = first_half_fails + second_half_fails
        if total_fails == 0:
            return None
        # If failures are heavily skewed to one half, likely order-dependent
        skew = abs(first_half_fails - second_half_fails) / total_fails
        if skew > 0.5:
            return CauseDetail(
                cause=RootCause.ORDER_DEPENDENCY,
                confidence=skew * 0.8,
                evidence=f"Failure skew={skew:.2f} across run halves",
            )
        return None

    def _check_shared_state(self, runs: list[TestRun]) -> CauseDetail | None:
        """Detect shared state: consecutive failures suggest shared state pollution."""
        consecutive_fails = 0
        max_consecutive = 0
        for r in runs:
            if not r.passed:
                consecutive_fails += 1
                max_consecutive = max(max_consecutive, consecutive_fails)
            else:
                consecutive_fails = 0
        if max_consecutive >= 3:
            confidence = min(1.0, max_consecutive / 5)
            return CauseDetail(
                cause=RootCause.SHARED_STATE,
                confidence=confidence,
                evidence=f"Max {max_consecutive} consecutive failures detected",
            )
        return None

    def _check_external_deps(self, runs: list[TestRun]) -> CauseDetail | None:
        """Detect external dependency: failures across different environments."""
        envs = {r.environment for r in runs}
        if len(envs) < 2:
            return None
        env_fail: dict[str, int] = {}
        env_total: dict[str, int] = {}
        for r in runs:
            env_total[r.environment] = env_total.get(r.environment, 0) + 1
            if not r.passed:
                env_fail[r.environment] = env_fail.get(r.environment, 0) + 1
        # If some envs fail and others don't
        env_rates = {
            e: env_fail.get(e, 0) / env_total[e] for e in envs
        }
        rates = list(env_rates.values())
        spread = max(rates) - min(rates)
        if spread > 0.3:
            return CauseDetail(
                cause=RootCause.EXTERNAL_DEPENDENCY,
                confidence=min(1.0, spread),
                evidence=f"Failure rate spread={spread:.2f} across environments",
            )
        return None

    @staticmethod
    def _recommend(cause: RootCause) -> str:
        recommendations = {
            RootCause.TIMING: "Add explicit waits or increase timeouts; avoid time-dependent assertions",
            RootCause.ORDER_DEPENDENCY: "Ensure proper test isolation; use setUp/tearDown to reset state",
            RootCause.SHARED_STATE: "Avoid shared mutable state; use fresh fixtures per test",
            RootCause.EXTERNAL_DEPENDENCY: "Mock external services; use dependency injection for testability",
            RootCause.RESOURCE_LEAK: "Ensure resources are cleaned up in tearDown/finally blocks",
            RootCause.UNKNOWN: "Investigate manually; consider running in isolation to narrow down",
        }
        return recommendations.get(cause, "Investigate manually")
