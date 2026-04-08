"""
E2E Test Planner — Plan E2E test suites with user journey mapping,
critical path identification, and priority ordering.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class Priority(Enum):
    """Test priority level."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class UserStep:
    """A single step in a user journey."""

    action: str
    target: str
    description: str = ""


@dataclass(frozen=True)
class UserJourney:
    """A complete user journey through the application."""

    name: str
    steps: tuple[UserStep, ...]
    priority: Priority = Priority.MEDIUM
    tags: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        """Stable hash-based identifier."""
        raw = f"{self.name}:{len(self.steps)}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class CriticalPath:
    """A critical path identified in the application."""

    name: str
    journeys: tuple[str, ...]  # journey names
    risk_score: float  # 0.0–1.0
    reason: str = ""


@dataclass(frozen=True)
class TestPlanEntry:
    """A single entry in the generated test plan."""

    journey_name: str
    priority: Priority
    estimated_duration_s: float
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class TestPlan:
    """Complete E2E test plan."""

    entries: tuple[TestPlanEntry, ...]
    total_estimated_duration_s: float
    critical_paths: tuple[CriticalPath, ...]
    coverage_score: float  # 0.0–1.0


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class E2ETestPlanner:
    """Plan E2E test suites from user journeys."""

    def __init__(
        self,
        *,
        default_step_duration_s: float = 5.0,
        critical_risk_threshold: float = 0.7,
    ) -> None:
        self._default_step_duration_s = default_step_duration_s
        self._critical_risk_threshold = critical_risk_threshold
        self._journeys: list[UserJourney] = []

    # -- Journey management --------------------------------------------------

    def add_journey(self, journey: UserJourney) -> E2ETestPlanner:
        """Add a journey (returns new planner for immutability of the call-site pattern)."""
        new = E2ETestPlanner(
            default_step_duration_s=self._default_step_duration_s,
            critical_risk_threshold=self._critical_risk_threshold,
        )
        new._journeys = [*self._journeys, journey]
        return new

    def add_journeys(self, journeys: list[UserJourney]) -> E2ETestPlanner:
        new = E2ETestPlanner(
            default_step_duration_s=self._default_step_duration_s,
            critical_risk_threshold=self._critical_risk_threshold,
        )
        new._journeys = [*self._journeys, *journeys]
        return new

    @property
    def journeys(self) -> list[UserJourney]:
        return list(self._journeys)

    # -- Critical path identification ----------------------------------------

    def identify_critical_paths(self) -> list[CriticalPath]:
        """Identify critical paths based on shared targets and priority."""
        target_map: dict[str, list[str]] = {}
        for j in self._journeys:
            for step in j.steps:
                target_map.setdefault(step.target, []).append(j.name)

        paths: list[CriticalPath] = []
        for target, journey_names in target_map.items():
            if len(journey_names) < 2:
                continue
            unique = tuple(sorted(set(journey_names)))
            risk = min(1.0, len(unique) / max(len(self._journeys), 1))
            if risk >= self._critical_risk_threshold:
                paths.append(
                    CriticalPath(
                        name=f"shared:{target}",
                        journeys=unique,
                        risk_score=round(risk, 3),
                        reason=f"Target '{target}' used by {len(unique)} journeys",
                    )
                )
        return sorted(paths, key=lambda p: p.risk_score, reverse=True)

    # -- Priority ordering ---------------------------------------------------

    _PRIORITY_ORDER = {
        Priority.CRITICAL: 0,
        Priority.HIGH: 1,
        Priority.MEDIUM: 2,
        Priority.LOW: 3,
    }

    def _estimate_duration(self, journey: UserJourney) -> float:
        return len(journey.steps) * self._default_step_duration_s

    def plan(self) -> TestPlan:
        """Generate a prioritised test plan."""
        if not self._journeys:
            return TestPlan(
                entries=(),
                total_estimated_duration_s=0.0,
                critical_paths=(),
                coverage_score=0.0,
            )

        critical = self.identify_critical_paths()
        critical_journey_names = set()
        for cp in critical:
            critical_journey_names.update(cp.journeys)

        entries: list[TestPlanEntry] = []
        for j in self._journeys:
            dur = self._estimate_duration(j)
            deps: list[str] = []
            for step in j.steps:
                for other in self._journeys:
                    if other.name != j.name and other.name not in deps:
                        if any(s.target == step.target for s in other.steps):
                            deps.append(other.name)
            entries.append(
                TestPlanEntry(
                    journey_name=j.name,
                    priority=j.priority,
                    estimated_duration_s=dur,
                    dependencies=tuple(deps),
                )
            )

        entries.sort(key=lambda e: self._PRIORITY_ORDER.get(e.priority, 99))

        total_dur = sum(e.estimated_duration_s for e in entries)
        coverage = min(1.0, len(self._journeys) / max(len(self._journeys), 1))

        return TestPlan(
            entries=tuple(entries),
            total_estimated_duration_s=round(total_dur, 2),
            critical_paths=tuple(critical),
            coverage_score=coverage,
        )
