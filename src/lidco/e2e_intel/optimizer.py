"""
E2E Test Optimizer — Optimize E2E suites for parallel execution,
shared setup, test isolation, and selective running.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class IsolationLevel(Enum):
    """Test isolation level."""

    NONE = "none"
    SHARED_STATE = "shared_state"
    FRESH_CONTEXT = "fresh_context"
    FULL_ISOLATION = "full_isolation"


@dataclass(frozen=True)
class TestMetadata:
    """Metadata about an E2E test for optimisation."""

    name: str
    duration_ms: float
    tags: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()
    last_result: str = "pass"  # pass / fail / skip


@dataclass(frozen=True)
class ParallelGroup:
    """A group of tests that can run in parallel."""

    group_id: int
    tests: tuple[str, ...]
    estimated_duration_ms: float


@dataclass(frozen=True)
class SharedSetup:
    """A shared setup step for multiple tests."""

    name: str
    tests: tuple[str, ...]
    setup_code: str = ""
    estimated_savings_ms: float = 0.0


@dataclass(frozen=True)
class SelectionResult:
    """Result of selective test running analysis."""

    selected: tuple[str, ...]
    skipped: tuple[str, ...]
    reason: str = ""


@dataclass(frozen=True)
class OptimizationReport:
    """Complete optimization report."""

    parallel_groups: tuple[ParallelGroup, ...]
    shared_setups: tuple[SharedSetup, ...]
    selection: SelectionResult
    isolation_recommendations: tuple[tuple[str, IsolationLevel], ...]
    estimated_speedup: float  # ratio, e.g. 2.0 means 2x faster
    original_duration_ms: float
    optimized_duration_ms: float


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------


class E2ETestOptimizer:
    """Optimize E2E test suites."""

    def __init__(
        self,
        *,
        max_parallel: int = 4,
        isolation_default: IsolationLevel = IsolationLevel.FRESH_CONTEXT,
    ) -> None:
        self._max_parallel = max_parallel
        self._isolation_default = isolation_default

    @property
    def max_parallel(self) -> int:
        return self._max_parallel

    # -- Parallel grouping ---------------------------------------------------

    def _build_dependency_set(
        self, tests: Sequence[TestMetadata]
    ) -> dict[str, set[str]]:
        """Build a map of test name -> all transitive dependencies."""
        dep_map: dict[str, set[str]] = {}
        for t in tests:
            dep_map[t.name] = set(t.depends_on)
        return dep_map

    def compute_parallel_groups(
        self, tests: Sequence[TestMetadata]
    ) -> list[ParallelGroup]:
        """Group tests for parallel execution respecting dependencies."""
        if not tests:
            return []

        deps = self._build_dependency_set(tests)
        by_name = {t.name: t for t in tests}
        assigned: set[str] = set()
        groups: list[ParallelGroup] = []
        group_id = 0

        remaining = [t.name for t in tests]
        while remaining:
            # Find tests whose deps are all assigned
            ready = [
                n for n in remaining if deps.get(n, set()).issubset(assigned)
            ]
            if not ready:
                # Break cycles by forcing remaining
                ready = remaining[:]

            # Chunk by max_parallel
            for i in range(0, len(ready), self._max_parallel):
                chunk = ready[i : i + self._max_parallel]
                dur = max(
                    (by_name[n].duration_ms for n in chunk if n in by_name),
                    default=0.0,
                )
                groups.append(
                    ParallelGroup(
                        group_id=group_id,
                        tests=tuple(chunk),
                        estimated_duration_ms=dur,
                    )
                )
                group_id += 1

            assigned.update(ready)
            remaining = [n for n in remaining if n not in assigned]

        return groups

    # -- Shared setup detection ----------------------------------------------

    def detect_shared_setups(
        self, tests: Sequence[TestMetadata]
    ) -> list[SharedSetup]:
        """Find tests that share tags and could share setup."""
        tag_map: dict[str, list[str]] = {}
        dur_map = {t.name: t.duration_ms for t in tests}

        for t in tests:
            for tag in t.tags:
                tag_map.setdefault(tag, []).append(t.name)

        setups: list[SharedSetup] = []
        for tag, names in sorted(tag_map.items()):
            if len(names) < 2:
                continue
            savings = sum(dur_map.get(n, 0) for n in names) * 0.1
            setups.append(
                SharedSetup(
                    name=f"shared_setup_{tag}",
                    tests=tuple(sorted(names)),
                    setup_code=f"# Shared setup for tag: {tag}",
                    estimated_savings_ms=round(savings, 2),
                )
            )
        return setups

    # -- Selective running ---------------------------------------------------

    def select_tests(
        self,
        tests: Sequence[TestMetadata],
        changed_files: Sequence[str],
    ) -> SelectionResult:
        """Select only tests affected by changed files."""
        if not changed_files:
            return SelectionResult(
                selected=tuple(t.name for t in tests),
                skipped=(),
                reason="No changed files — running all tests",
            )

        changed = set(changed_files)
        selected: list[str] = []
        skipped: list[str] = []

        for t in tests:
            if set(t.changed_files) & changed:
                selected.append(t.name)
            elif t.last_result == "fail":
                # Always re-run previously failing tests
                selected.append(t.name)
            else:
                skipped.append(t.name)

        if not selected:
            # Fall back to all
            return SelectionResult(
                selected=tuple(t.name for t in tests),
                skipped=(),
                reason="No direct matches — running all tests as fallback",
            )

        return SelectionResult(
            selected=tuple(selected),
            skipped=tuple(skipped),
            reason=f"Selected {len(selected)} test(s) affected by {len(changed)} file(s)",
        )

    # -- Isolation recommendations -------------------------------------------

    def recommend_isolation(
        self, tests: Sequence[TestMetadata]
    ) -> list[tuple[str, IsolationLevel]]:
        """Recommend isolation level for each test."""
        recs: list[tuple[str, IsolationLevel]] = []
        for t in tests:
            if t.depends_on:
                recs.append((t.name, IsolationLevel.SHARED_STATE))
            elif t.last_result == "fail":
                recs.append((t.name, IsolationLevel.FULL_ISOLATION))
            else:
                recs.append((t.name, self._isolation_default))
        return recs

    # -- Full optimization ---------------------------------------------------

    def optimize(
        self,
        tests: Sequence[TestMetadata],
        *,
        changed_files: Sequence[str] = (),
    ) -> OptimizationReport:
        """Run full optimisation pipeline."""
        if not tests:
            return OptimizationReport(
                parallel_groups=(),
                shared_setups=(),
                selection=SelectionResult(selected=(), skipped=()),
                isolation_recommendations=(),
                estimated_speedup=1.0,
                original_duration_ms=0.0,
                optimized_duration_ms=0.0,
            )

        groups = self.compute_parallel_groups(tests)
        setups = self.detect_shared_setups(tests)
        selection = self.select_tests(tests, changed_files)
        isolation = self.recommend_isolation(tests)

        original = sum(t.duration_ms for t in tests)
        optimized = sum(g.estimated_duration_ms for g in groups)
        savings_from_setups = sum(s.estimated_savings_ms for s in setups)
        optimized = max(optimized - savings_from_setups, 1.0)
        speedup = round(original / optimized, 2) if optimized > 0 else 1.0

        return OptimizationReport(
            parallel_groups=tuple(groups),
            shared_setups=tuple(setups),
            selection=selection,
            isolation_recommendations=tuple(isolation),
            estimated_speedup=speedup,
            original_duration_ms=round(original, 2),
            optimized_duration_ms=round(optimized, 2),
        )
