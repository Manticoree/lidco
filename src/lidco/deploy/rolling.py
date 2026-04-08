"""RollingDeployer — rolling updates with batch size, health checks, pause on error,
resume, and configurable speed (stdlib only)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class RollingState(str, Enum):
    """Lifecycle states for a rolling deployment."""

    IDLE = "idle"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass(frozen=True)
class InstanceHealth:
    """Health of one instance."""

    instance_id: str
    healthy: bool
    detail: str = ""


@dataclass
class BatchResult:
    """Outcome of deploying one batch."""

    batch_index: int
    instance_ids: list[str] = field(default_factory=list)
    success: bool = True
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class RollingConfig:
    """Configuration for rolling updates."""

    batch_size: int = 1
    max_unavailable: int = 1
    pause_on_error: bool = True
    health_retries: int = 3
    health_interval_s: float = 1.0
    inter_batch_delay_s: float = 0.0


@dataclass
class RollingDeployment:
    """Record of a rolling deployment."""

    deployment_id: str = ""
    version: str = ""
    state: RollingState = RollingState.IDLE
    total_instances: int = 0
    updated_instances: int = 0
    batches: list[BatchResult] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""
    logs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.deployment_id:
            self.deployment_id = uuid.uuid4().hex

    @property
    def progress_pct(self) -> float:
        if self.total_instances == 0:
            return 0.0
        return (self.updated_instances / self.total_instances) * 100.0

    @property
    def duration_ms(self) -> float:
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at) * 1000
        return 0.0


class RollingDeployer:
    """Manages rolling deployments across a set of instances."""

    def __init__(
        self,
        config: Optional[RollingConfig] = None,
        deploy_fn: Optional[Callable[[str, str], bool]] = None,
        health_fn: Optional[Callable[[str], InstanceHealth]] = None,
        rollback_fn: Optional[Callable[[str, str], bool]] = None,
    ) -> None:
        self._config = config or RollingConfig()
        self._deploy_fn = deploy_fn or self._default_deploy
        self._health_fn = health_fn or self._default_health
        self._rollback_fn = rollback_fn or self._default_rollback
        self._current: Optional[RollingDeployment] = None
        self._history: list[RollingDeployment] = []
        self._paused_at_batch: int = -1

    @property
    def current(self) -> Optional[RollingDeployment]:
        return self._current

    @property
    def history(self) -> list[RollingDeployment]:
        return list(self._history)

    @property
    def config(self) -> RollingConfig:
        return self._config

    def deploy(self, version: str, instances: list[str]) -> RollingDeployment:
        """Deploy *version* across *instances* in batches."""
        dep = RollingDeployment(
            version=version,
            state=RollingState.IN_PROGRESS,
            total_instances=len(instances),
            started_at=time.time(),
        )
        self._current = dep
        self._paused_at_batch = -1
        dep.logs.append(f"Rolling deploy of {version} to {len(instances)} instances (batch_size={self._config.batch_size})")

        batches = self._make_batches(instances)
        for i, batch in enumerate(batches):
            result = self._deploy_batch(i, batch, version, dep)
            dep.batches.append(result)

            if result.success:
                dep.updated_instances += len(batch)
                dep.logs.append(f"Batch {i + 1}/{len(batches)} succeeded ({len(batch)} instances)")
            else:
                dep.logs.append(f"Batch {i + 1}/{len(batches)} failed: {result.error}")
                if self._config.pause_on_error:
                    dep.state = RollingState.PAUSED
                    self._paused_at_batch = i
                    dep.logs.append("Paused — resolve issue then call resume()")
                    return dep
                dep.state = RollingState.FAILED
                dep.error = result.error
                dep.finished_at = time.time()
                self._history.append(dep)
                self._current = None
                return dep

            if self._config.inter_batch_delay_s > 0 and i < len(batches) - 1:
                time.sleep(self._config.inter_batch_delay_s)

        dep.state = RollingState.COMPLETED
        dep.finished_at = time.time()
        dep.logs.append("Rolling deploy completed")
        self._history.append(dep)
        self._current = None
        return dep

    def resume(self, instances: list[str]) -> Optional[RollingDeployment]:
        """Resume a paused deployment from the failed batch onward."""
        dep = self._current
        if dep is None or dep.state != RollingState.PAUSED:
            return None

        dep.state = RollingState.IN_PROGRESS
        dep.logs.append("Resuming deployment")

        batches = self._make_batches(instances)
        start = self._paused_at_batch
        if start < 0:
            start = 0

        for i in range(start, len(batches)):
            batch = batches[i]
            result = self._deploy_batch(i, batch, dep.version, dep)
            # Replace batch result if retrying same index
            if i < len(dep.batches):
                dep.batches[i] = result
            else:
                dep.batches.append(result)

            if result.success:
                dep.updated_instances += len(batch)
                dep.logs.append(f"Batch {i + 1}/{len(batches)} succeeded on resume")
            else:
                dep.logs.append(f"Batch {i + 1}/{len(batches)} failed on resume: {result.error}")
                if self._config.pause_on_error:
                    dep.state = RollingState.PAUSED
                    self._paused_at_batch = i
                    return dep
                dep.state = RollingState.FAILED
                dep.error = result.error
                dep.finished_at = time.time()
                self._history.append(dep)
                self._current = None
                return dep

        dep.state = RollingState.COMPLETED
        dep.finished_at = time.time()
        dep.logs.append("Rolling deploy completed after resume")
        self._history.append(dep)
        self._current = None
        return dep

    def rollback(self, instances: list[str], previous_version: str) -> Optional[RollingDeployment]:
        """Roll back all instances to *previous_version*."""
        dep = self._current or RollingDeployment(
            version=previous_version,
            state=RollingState.ROLLING_BACK,
            total_instances=len(instances),
            started_at=time.time(),
        )
        dep.state = RollingState.ROLLING_BACK
        dep.logs.append(f"Rolling back to {previous_version}")

        all_ok = True
        for inst in instances:
            try:
                ok = self._rollback_fn(inst, previous_version)
                if not ok:
                    all_ok = False
            except Exception as exc:  # noqa: BLE001
                dep.logs.append(f"Rollback failed for {inst}: {exc}")
                all_ok = False

        if all_ok:
            dep.state = RollingState.ROLLED_BACK
            dep.logs.append("Rollback completed")
        else:
            dep.state = RollingState.FAILED
            dep.error = "Some instances failed to rollback"
            dep.logs.append("Rollback partially failed")

        dep.finished_at = time.time()
        self._history.append(dep)
        self._current = None
        return dep

    def pause(self) -> bool:
        """Manually pause the current deployment."""
        if self._current and self._current.state == RollingState.IN_PROGRESS:
            self._current.state = RollingState.PAUSED
            self._current.logs.append("Manually paused")
            return True
        return False

    def status(self) -> dict[str, Any]:
        if self._current:
            return {
                "state": self._current.state.value,
                "version": self._current.version,
                "progress": f"{self._current.updated_instances}/{self._current.total_instances}",
                "progress_pct": round(self._current.progress_pct, 1),
            }
        return {"state": "idle", "version": "", "progress": "0/0", "progress_pct": 0.0}

    # -- internals ----------------------------------------------------------

    def _make_batches(self, instances: list[str]) -> list[list[str]]:
        bs = max(1, self._config.batch_size)
        return [instances[i : i + bs] for i in range(0, len(instances), bs)]

    def _deploy_batch(
        self, index: int, batch: list[str], version: str, dep: RollingDeployment
    ) -> BatchResult:
        start = time.time()
        for inst in batch:
            try:
                ok = self._deploy_fn(inst, version)
            except Exception as exc:  # noqa: BLE001
                return BatchResult(
                    batch_index=index,
                    instance_ids=batch,
                    success=False,
                    error=str(exc),
                    duration_ms=(time.time() - start) * 1000,
                )
            if not ok:
                return BatchResult(
                    batch_index=index,
                    instance_ids=batch,
                    success=False,
                    error=f"deploy_fn returned False for {inst}",
                    duration_ms=(time.time() - start) * 1000,
                )

        # health checks
        for inst in batch:
            if not self._check_instance_health(inst):
                return BatchResult(
                    batch_index=index,
                    instance_ids=batch,
                    success=False,
                    error=f"Health check failed for {inst}",
                    duration_ms=(time.time() - start) * 1000,
                )

        return BatchResult(
            batch_index=index,
            instance_ids=batch,
            success=True,
            duration_ms=(time.time() - start) * 1000,
        )

    def _check_instance_health(self, instance_id: str) -> bool:
        for attempt in range(self._config.health_retries):
            result = self._health_fn(instance_id)
            if result.healthy:
                return True
            if attempt < self._config.health_retries - 1:
                time.sleep(self._config.health_interval_s)
        return False

    @staticmethod
    def _default_deploy(_instance: str, _version: str) -> bool:
        return True

    @staticmethod
    def _default_health(instance_id: str) -> InstanceHealth:
        return InstanceHealth(instance_id=instance_id, healthy=True)

    @staticmethod
    def _default_rollback(_instance: str, _version: str) -> bool:
        return True
