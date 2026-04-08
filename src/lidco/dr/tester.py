"""
DR Test Runner -- simulate DR scenarios, measure recovery time,
validate data integrity, chaos-based testing.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ScenarioType(Enum):
    """Type of DR test scenario."""

    FULL_FAILOVER = "full_failover"
    PARTIAL_FAILURE = "partial_failure"
    DATA_CORRUPTION = "data_corruption"
    NETWORK_PARTITION = "network_partition"
    REGION_OUTAGE = "region_outage"
    BACKUP_RESTORE = "backup_restore"
    CHAOS = "chaos"


class DRTestStatus(Enum):
    """Status of a DR test."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True)
class ScenarioConfig:
    """Configuration for a DR test scenario."""

    scenario_type: ScenarioType
    name: str = ""
    timeout_seconds: int = 300
    chaos_intensity: float = 0.5
    target_components: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 0.0 <= self.chaos_intensity <= 1.0:
            raise ValueError("chaos_intensity must be between 0.0 and 1.0")


@dataclass
class IntegrityResult:
    """Result of a data integrity check."""

    component: str
    is_valid: bool
    expected_checksum: str = ""
    actual_checksum: str = ""
    records_checked: int = 0
    records_corrupted: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DRTestResult:
    """Result of a DR test run."""

    test_id: str
    scenario_type: ScenarioType
    status: DRTestStatus
    started_at: float
    completed_at: float = 0.0
    recovery_time_seconds: float = 0.0
    data_integrity: list[IntegrityResult] = field(default_factory=list)
    steps_completed: int = 0
    steps_total: int = 0
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return 0.0

    @property
    def all_integrity_valid(self) -> bool:
        return all(ir.is_valid for ir in self.data_integrity) if self.data_integrity else True

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "scenario_type": self.scenario_type.value,
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "recovery_time_seconds": self.recovery_time_seconds,
            "data_integrity_valid": self.all_integrity_valid,
            "steps_completed": self.steps_completed,
            "steps_total": self.steps_total,
            "error": self.error,
        }


@dataclass
class DRTestScenario:
    """A runnable DR test scenario."""

    scenario_id: str
    config: ScenarioConfig
    steps: list[Callable[[], bool]] = field(default_factory=list)
    integrity_checks: list[Callable[[], IntegrityResult]] = field(default_factory=list)

    def add_step(self, step: Callable[[], bool]) -> None:
        self.steps.append(step)

    def add_integrity_check(self, check: Callable[[], IntegrityResult]) -> None:
        self.integrity_checks.append(check)


class DRTestRunner:
    """Runs DR test scenarios, measuring recovery time and validating integrity."""

    def __init__(self) -> None:
        self._scenarios: dict[str, DRTestScenario] = {}
        self._results: list[DRTestResult] = []

    def create_scenario(self, config: ScenarioConfig) -> DRTestScenario:
        """Create a new test scenario."""
        scenario_id = uuid.uuid4().hex[:12]
        scenario = DRTestScenario(
            scenario_id=scenario_id,
            config=config,
        )
        self._scenarios[scenario_id] = scenario
        return scenario

    def get_scenario(self, scenario_id: str) -> DRTestScenario | None:
        return self._scenarios.get(scenario_id)

    @property
    def scenarios(self) -> dict[str, DRTestScenario]:
        return dict(self._scenarios)

    @property
    def results(self) -> list[DRTestResult]:
        return list(self._results)

    def run_scenario(self, scenario_id: str) -> DRTestResult:
        """Execute a test scenario and return the result."""
        scenario = self._scenarios.get(scenario_id)
        if scenario is None:
            result = DRTestResult(
                test_id=uuid.uuid4().hex[:12],
                scenario_type=ScenarioType.CHAOS,
                status=DRTestStatus.ERROR,
                started_at=time.time(),
                completed_at=time.time(),
                error=f"Scenario not found: {scenario_id}",
            )
            self._results.append(result)
            return result

        test_id = uuid.uuid4().hex[:12]
        start = time.time()
        steps_completed = 0
        steps_total = len(scenario.steps)

        try:
            for step_fn in scenario.steps:
                elapsed = time.time() - start
                if elapsed > scenario.config.timeout_seconds:
                    result = DRTestResult(
                        test_id=test_id,
                        scenario_type=scenario.config.scenario_type,
                        status=DRTestStatus.FAILED,
                        started_at=start,
                        completed_at=time.time(),
                        recovery_time_seconds=elapsed,
                        steps_completed=steps_completed,
                        steps_total=steps_total,
                        error="Timeout exceeded",
                    )
                    self._results.append(result)
                    return result

                ok = step_fn()
                if ok:
                    steps_completed += 1
                else:
                    result = DRTestResult(
                        test_id=test_id,
                        scenario_type=scenario.config.scenario_type,
                        status=DRTestStatus.FAILED,
                        started_at=start,
                        completed_at=time.time(),
                        recovery_time_seconds=time.time() - start,
                        steps_completed=steps_completed,
                        steps_total=steps_total,
                        error=f"Step {steps_completed + 1} failed",
                    )
                    self._results.append(result)
                    return result

            recovery_time = time.time() - start

            integrity_results: list[IntegrityResult] = []
            for check_fn in scenario.integrity_checks:
                integrity_results.append(check_fn())

            all_valid = all(ir.is_valid for ir in integrity_results) if integrity_results else True

            result = DRTestResult(
                test_id=test_id,
                scenario_type=scenario.config.scenario_type,
                status=DRTestStatus.PASSED if all_valid else DRTestStatus.FAILED,
                started_at=start,
                completed_at=time.time(),
                recovery_time_seconds=recovery_time,
                data_integrity=integrity_results,
                steps_completed=steps_completed,
                steps_total=steps_total,
                error="" if all_valid else "Data integrity check failed",
            )
            self._results.append(result)
            return result

        except Exception as exc:
            result = DRTestResult(
                test_id=test_id,
                scenario_type=scenario.config.scenario_type,
                status=DRTestStatus.ERROR,
                started_at=start,
                completed_at=time.time(),
                recovery_time_seconds=time.time() - start,
                steps_completed=steps_completed,
                steps_total=steps_total,
                error=str(exc),
            )
            self._results.append(result)
            return result

    def run_all(self) -> list[DRTestResult]:
        """Run all registered scenarios."""
        return [self.run_scenario(sid) for sid in self._scenarios]

    def get_summary(self) -> dict[str, Any]:
        """Return a summary of all test results."""
        passed = sum(1 for r in self._results if r.status == DRTestStatus.PASSED)
        failed = sum(1 for r in self._results if r.status == DRTestStatus.FAILED)
        errors = sum(1 for r in self._results if r.status == DRTestStatus.ERROR)
        avg_recovery = 0.0
        if self._results:
            avg_recovery = sum(r.recovery_time_seconds for r in self._results) / len(self._results)

        return {
            "total": len(self._results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "avg_recovery_seconds": round(avg_recovery, 3),
        }

    @staticmethod
    def compute_checksum(data: bytes) -> str:
        """Compute SHA-256 checksum for data integrity verification."""
        return hashlib.sha256(data).hexdigest()
