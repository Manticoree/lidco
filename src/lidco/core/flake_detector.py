"""Flaky test detector — core data model for tracking test outcome history.

Tracks outcomes across multiple test runs, computes flake rates, and surfaces
the most unreliable tests for prioritised investigation.

Usage::

    from lidco.core.flake_detector import FlakeHistory, TestOutcome

    h = FlakeHistory()
    h.record_outcome(TestOutcome("tests/test_foo.py::test_bar", passed=False,
                                  duration_s=0.3, error_msg="AssertionError"))
    h.record_outcome(TestOutcome("tests/test_foo.py::test_bar", passed=True,
                                  duration_s=0.1, error_msg=None))
    for rec in h.get_flaky_tests(min_flake_rate=0.1, min_runs=2):
        print(rec.test_id, rec.flake_rate)
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TestOutcome:
    """A single test execution result.

    Attributes:
        test_id:    Unique test identifier (e.g. ``"tests/test_foo.py::test_bar"``).
        passed:     ``True`` when the test passed, ``False`` when it failed.
        duration_s: Wall-clock execution time in seconds.
        error_msg:  Short error/exception message, or ``None`` when passed.
    """

    # Prevent pytest from collecting this class as a test suite.
    __test__ = False

    test_id: str
    passed: bool
    duration_s: float
    error_msg: str | None


@dataclass(frozen=True)
class FlakeRecord:
    """Aggregated flakiness statistics for a single test.

    Attributes:
        test_id:    Unique test identifier.
        runs:       Total number of times the test was executed.
        failures:   Number of failing runs.
        flake_rate: ``failures / runs`` in ``[0.0, 1.0]``.
    """

    test_id: str
    runs: int
    failures: int
    flake_rate: float


# ---------------------------------------------------------------------------
# Internal mutable accumulator (not exposed publicly)
# ---------------------------------------------------------------------------


@dataclass
class _TestStats:
    """Mutable per-test accumulator used internally by FlakeHistory."""

    runs: int = 0
    failures: int = 0

    def record(self, passed: bool) -> None:
        self.runs += 1
        if not passed:
            self.failures += 1

    def to_record(self, test_id: str) -> FlakeRecord:
        rate = self.failures / self.runs if self.runs > 0 else 0.0
        return FlakeRecord(
            test_id=test_id,
            runs=self.runs,
            failures=self.failures,
            flake_rate=rate,
        )


# ---------------------------------------------------------------------------
# FlakeHistory
# ---------------------------------------------------------------------------


class FlakeHistory:
    """In-memory store for test outcome history across multiple runs.

    Thread-safety: not thread-safe.  Intended for single-threaded use from
    within the test runner loop.
    """

    def __init__(self) -> None:
        self._stats: dict[str, _TestStats] = {}
        self._total_runs: int = 0

    # ── Mutation ──────────────────────────────────────────────────────────

    def record_outcome(self, outcome: TestOutcome) -> None:
        """Record a single test execution outcome.

        Args:
            outcome: A :class:`TestOutcome` describing one test execution.
        """
        if outcome.test_id not in self._stats:
            self._stats[outcome.test_id] = _TestStats()
        self._stats[outcome.test_id].record(outcome.passed)
        self._total_runs += 1

    def clear(self) -> None:
        """Reset all history."""
        self._stats = {}
        self._total_runs = 0

    # ── Queries ───────────────────────────────────────────────────────────

    def get_record(self, test_id: str) -> FlakeRecord | None:
        """Return the :class:`FlakeRecord` for *test_id*, or ``None`` if unknown."""
        stats = self._stats.get(test_id)
        if stats is None:
            return None
        return stats.to_record(test_id)

    def get_all_records(self) -> list[FlakeRecord]:
        """Return :class:`FlakeRecord` objects for every tracked test."""
        return [s.to_record(tid) for tid, s in self._stats.items()]

    def get_flaky_tests(
        self,
        min_flake_rate: float = 0.1,
        min_runs: int = 1,
    ) -> list[FlakeRecord]:
        """Return tests whose flake rate meets the given thresholds.

        Results are sorted by flake rate descending (most flaky first).

        Args:
            min_flake_rate: Minimum flake rate to include (default 0.1 = 10%).
            min_runs:       Minimum number of runs required (filters out
                            one-off observations).
        """
        results = [
            s.to_record(tid)
            for tid, s in self._stats.items()
            if s.runs >= min_runs and (s.failures / s.runs) >= min_flake_rate
        ]
        results.sort(key=lambda r: r.flake_rate, reverse=True)
        return results

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def total_runs(self) -> int:
        """Total number of individual test executions recorded."""
        return self._total_runs

    @property
    def total_tests(self) -> int:
        """Number of distinct test IDs tracked."""
        return len(self._stats)
