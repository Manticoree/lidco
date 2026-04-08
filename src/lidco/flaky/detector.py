"""
Flaky test detector — detect flaky tests from test history.

Pass/fail ratio, timing variance, environment sensitivity.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class FlakySeverity(Enum):
    """Severity classification for flaky tests."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class TestRun:
    """A single test execution record."""

    test_name: str
    passed: bool
    duration_ms: float = 0.0
    environment: str = "default"
    timestamp: str = ""


@dataclass(frozen=True)
class FlakyTestResult:
    """Detection result for a single test."""

    test_name: str
    total_runs: int
    pass_count: int
    fail_count: int
    pass_rate: float
    timing_variance: float
    environments: list[str] = field(default_factory=list)
    is_flaky: bool = False
    severity: FlakySeverity = FlakySeverity.LOW
    environment_sensitive: bool = False


@dataclass(frozen=True)
class DetectionReport:
    """Summary of flaky test detection."""

    total_tests: int
    flaky_count: int
    results: list[FlakyTestResult] = field(default_factory=list)
    flaky_rate: float = 0.0


class FlakyDetector:
    """Detect flaky tests from test execution history.

    Parameters
    ----------
    min_runs : int
        Minimum number of runs required to classify a test (default 3).
    flaky_threshold : float
        Pass rate below this but above 0.0 is considered flaky (default 0.95).
    timing_cv_threshold : float
        Coefficient-of-variation threshold for timing (default 0.5).
    """

    def __init__(
        self,
        *,
        min_runs: int = 3,
        flaky_threshold: float = 0.95,
        timing_cv_threshold: float = 0.5,
    ) -> None:
        self._min_runs = max(1, min_runs)
        self._flaky_threshold = flaky_threshold
        self._timing_cv_threshold = timing_cv_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, runs: Sequence[TestRun]) -> DetectionReport:
        """Analyse *runs* and return a detection report."""
        grouped: dict[str, list[TestRun]] = {}
        for r in runs:
            grouped.setdefault(r.test_name, []).append(r)

        results: list[FlakyTestResult] = []
        for name, test_runs in sorted(grouped.items()):
            result = self._analyse_test(name, test_runs)
            results.append(result)

        flaky = [r for r in results if r.is_flaky]
        total = len(results)
        return DetectionReport(
            total_tests=total,
            flaky_count=len(flaky),
            results=results,
            flaky_rate=len(flaky) / total if total else 0.0,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _analyse_test(self, name: str, runs: list[TestRun]) -> FlakyTestResult:
        total = len(runs)
        pass_count = sum(1 for r in runs if r.passed)
        fail_count = total - pass_count
        pass_rate = pass_count / total if total else 0.0

        durations = [r.duration_ms for r in runs if r.duration_ms > 0]
        if len(durations) >= 2:
            mean = statistics.mean(durations)
            stdev = statistics.stdev(durations)
            timing_variance = stdev / mean if mean > 0 else 0.0
        else:
            timing_variance = 0.0

        envs = sorted({r.environment for r in runs})
        env_sensitive = self._check_env_sensitivity(runs, envs)

        is_flaky = False
        if total >= self._min_runs:
            # Mixed pass/fail
            if 0 < pass_rate < self._flaky_threshold:
                is_flaky = True
            # High timing variance
            if timing_variance > self._timing_cv_threshold and fail_count > 0:
                is_flaky = True
            # Environment sensitivity
            if env_sensitive:
                is_flaky = True

        severity = self._classify_severity(pass_rate, timing_variance, is_flaky)

        return FlakyTestResult(
            test_name=name,
            total_runs=total,
            pass_count=pass_count,
            fail_count=fail_count,
            pass_rate=pass_rate,
            timing_variance=timing_variance,
            environments=envs,
            is_flaky=is_flaky,
            severity=severity,
            environment_sensitive=env_sensitive,
        )

    def _check_env_sensitivity(
        self, runs: list[TestRun], envs: list[str]
    ) -> bool:
        if len(envs) < 2:
            return False
        env_pass_rates: dict[str, float] = {}
        for env in envs:
            env_runs = [r for r in runs if r.environment == env]
            if env_runs:
                env_pass_rates[env] = sum(1 for r in env_runs if r.passed) / len(
                    env_runs
                )
        if len(env_pass_rates) < 2:
            return False
        rates = list(env_pass_rates.values())
        return (max(rates) - min(rates)) > 0.3

    @staticmethod
    def _classify_severity(
        pass_rate: float, timing_variance: float, is_flaky: bool
    ) -> FlakySeverity:
        if not is_flaky:
            return FlakySeverity.LOW
        if pass_rate < 0.3:
            return FlakySeverity.CRITICAL
        if pass_rate < 0.6:
            return FlakySeverity.HIGH
        if pass_rate < 0.85:
            return FlakySeverity.MEDIUM
        return FlakySeverity.LOW
