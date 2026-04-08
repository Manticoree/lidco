"""
Chaos Experiments — define chaos experiments with configurable duration/scope.

Supports network delay, disk full, service down, and custom experiment types.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExperimentType(Enum):
    """Types of chaos experiments."""

    NETWORK_DELAY = "network_delay"
    DISK_FULL = "disk_full"
    SERVICE_DOWN = "service_down"
    CPU_SPIKE = "cpu_spike"
    MEMORY_PRESSURE = "memory_pressure"
    CUSTOM = "custom"


class ExperimentStatus(Enum):
    """Status of a chaos experiment."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass(frozen=True)
class ExperimentConfig:
    """Configuration for a chaos experiment."""

    experiment_type: ExperimentType
    duration_seconds: float = 30.0
    scope: str = "local"
    intensity: float = 0.5
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError("intensity must be between 0.0 and 1.0")


@dataclass
class ExperimentResult:
    """Result of a completed chaos experiment."""

    experiment_id: str
    experiment_type: ExperimentType
    status: ExperimentStatus
    started_at: float
    ended_at: float
    errors_observed: int = 0
    recovery_time_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        return self.ended_at - self.started_at


@dataclass
class Experiment:
    """A single chaos experiment instance."""

    id: str
    config: ExperimentConfig
    status: ExperimentStatus = ExperimentStatus.PENDING
    started_at: float = 0.0
    ended_at: float = 0.0
    errors_observed: int = 0
    details: dict[str, Any] = field(default_factory=dict)


class ChaosExperimentRunner:
    """Define and run chaos experiments."""

    def __init__(self) -> None:
        self._experiments: dict[str, Experiment] = {}
        self._history: list[ExperimentResult] = []

    def create_experiment(self, config: ExperimentConfig) -> Experiment:
        """Create a new chaos experiment from config."""
        exp = Experiment(
            id=uuid.uuid4().hex[:12],
            config=config,
        )
        self._experiments = {**self._experiments, exp.id: exp}
        return exp

    def start_experiment(self, experiment_id: str) -> Experiment:
        """Start a pending experiment."""
        exp = self._experiments.get(experiment_id)
        if exp is None:
            raise KeyError(f"Experiment {experiment_id!r} not found")
        if exp.status != ExperimentStatus.PENDING:
            raise RuntimeError(
                f"Cannot start experiment in {exp.status.value} state"
            )
        updated = Experiment(
            id=exp.id,
            config=exp.config,
            status=ExperimentStatus.RUNNING,
            started_at=time.time(),
            details={**exp.details},
        )
        self._experiments = {**self._experiments, exp.id: updated}
        return updated

    def complete_experiment(
        self,
        experiment_id: str,
        *,
        errors_observed: int = 0,
        recovery_time: float = 0.0,
        details: dict[str, Any] | None = None,
    ) -> ExperimentResult:
        """Mark a running experiment as completed and record results."""
        exp = self._experiments.get(experiment_id)
        if exp is None:
            raise KeyError(f"Experiment {experiment_id!r} not found")
        if exp.status != ExperimentStatus.RUNNING:
            raise RuntimeError(
                f"Cannot complete experiment in {exp.status.value} state"
            )

        ended = time.time()
        result = ExperimentResult(
            experiment_id=exp.id,
            experiment_type=exp.config.experiment_type,
            status=ExperimentStatus.COMPLETED,
            started_at=exp.started_at,
            ended_at=ended,
            errors_observed=errors_observed,
            recovery_time_seconds=recovery_time,
            details=details or {},
        )

        updated = Experiment(
            id=exp.id,
            config=exp.config,
            status=ExperimentStatus.COMPLETED,
            started_at=exp.started_at,
            ended_at=ended,
            errors_observed=errors_observed,
            details=details or {},
        )
        self._experiments = {**self._experiments, exp.id: updated}
        self._history = [*self._history, result]
        return result

    def abort_experiment(self, experiment_id: str) -> Experiment:
        """Abort a running experiment."""
        exp = self._experiments.get(experiment_id)
        if exp is None:
            raise KeyError(f"Experiment {experiment_id!r} not found")
        if exp.status != ExperimentStatus.RUNNING:
            raise RuntimeError(
                f"Cannot abort experiment in {exp.status.value} state"
            )
        updated = Experiment(
            id=exp.id,
            config=exp.config,
            status=ExperimentStatus.ABORTED,
            started_at=exp.started_at,
            ended_at=time.time(),
            details={**exp.details},
        )
        self._experiments = {**self._experiments, exp.id: updated}
        return updated

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        return self._experiments.get(experiment_id)

    def list_experiments(
        self, *, status: ExperimentStatus | None = None
    ) -> list[Experiment]:
        """List experiments, optionally filtered by status."""
        exps = list(self._experiments.values())
        if status is not None:
            exps = [e for e in exps if e.status == status]
        return exps

    @property
    def history(self) -> list[ExperimentResult]:
        return list(self._history)
