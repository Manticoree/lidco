"""CanaryDeployer — canary releases with percentage rollout, metric monitoring,
auto-promote/rollback, and traffic splitting (stdlib only)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class CanaryState(str, Enum):
    """Lifecycle states for a canary deployment."""

    IDLE = "idle"
    RAMPING = "ramping"
    MONITORING = "monitoring"
    PROMOTED = "promoted"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass(frozen=True)
class CanaryMetrics:
    """Snapshot of canary health metrics."""

    error_rate: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    healthy: bool = True


@dataclass
class TrafficSplit:
    """Current traffic allocation."""

    canary_pct: float = 0.0
    stable_pct: float = 100.0

    def __post_init__(self) -> None:
        self.stable_pct = 100.0 - self.canary_pct


@dataclass
class CanaryDeployment:
    """Record of a canary deployment."""

    deployment_id: str = ""
    version: str = ""
    state: CanaryState = CanaryState.IDLE
    traffic: TrafficSplit = field(default_factory=TrafficSplit)
    steps_completed: int = 0
    total_steps: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""
    logs: list[str] = field(default_factory=list)
    metrics_history: list[CanaryMetrics] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.deployment_id:
            self.deployment_id = uuid.uuid4().hex

    @property
    def duration_ms(self) -> float:
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at) * 1000
        return 0.0


@dataclass
class CanaryConfig:
    """Configuration for a canary rollout."""

    steps: list[float] = field(default_factory=lambda: [5.0, 25.0, 50.0, 100.0])
    monitor_interval_s: float = 5.0
    error_rate_threshold: float = 0.05
    latency_threshold_ms: float = 500.0
    auto_promote: bool = True
    auto_rollback: bool = True


class CanaryDeployer:
    """Manages canary deployments with gradual traffic shifting."""

    def __init__(
        self,
        config: Optional[CanaryConfig] = None,
        deploy_fn: Optional[Callable[[str, float], bool]] = None,
        metrics_fn: Optional[Callable[[str], CanaryMetrics]] = None,
        rollback_fn: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self._config = config or CanaryConfig()
        self._deploy_fn = deploy_fn or self._default_deploy
        self._metrics_fn = metrics_fn or self._default_metrics
        self._rollback_fn = rollback_fn or self._default_rollback
        self._current: Optional[CanaryDeployment] = None
        self._history: list[CanaryDeployment] = []

    @property
    def current(self) -> Optional[CanaryDeployment]:
        return self._current

    @property
    def history(self) -> list[CanaryDeployment]:
        return list(self._history)

    @property
    def config(self) -> CanaryConfig:
        return self._config

    def deploy(self, version: str) -> CanaryDeployment:
        """Start a canary rollout for *version* through configured percentage steps."""
        dep = CanaryDeployment(
            version=version,
            state=CanaryState.RAMPING,
            total_steps=len(self._config.steps),
            started_at=time.time(),
        )
        self._current = dep
        dep.logs.append(f"Starting canary deploy of {version}")

        for i, pct in enumerate(self._config.steps):
            dep.logs.append(f"Step {i + 1}/{dep.total_steps}: shifting {pct}% traffic to canary")

            # shift traffic
            try:
                ok = self._deploy_fn(version, pct)
            except Exception as exc:  # noqa: BLE001
                dep.state = CanaryState.FAILED
                dep.error = str(exc)
                dep.finished_at = time.time()
                self._history.append(dep)
                self._current = None
                return dep

            if not ok:
                dep.state = CanaryState.FAILED
                dep.error = f"deploy_fn failed at {pct}%"
                dep.finished_at = time.time()
                self._history.append(dep)
                self._current = None
                return dep

            dep.traffic = TrafficSplit(canary_pct=pct)
            dep.steps_completed = i + 1

            # monitor
            dep.state = CanaryState.MONITORING
            metrics = self._metrics_fn(version)
            dep.metrics_history.append(metrics)

            if not self._is_healthy(metrics):
                dep.logs.append(f"Unhealthy metrics at {pct}%: error_rate={metrics.error_rate}")
                if self._config.auto_rollback:
                    return self._do_rollback(dep, f"Metrics exceeded threshold at {pct}%")
                dep.state = CanaryState.FAILED
                dep.error = f"Unhealthy at {pct}%"
                dep.finished_at = time.time()
                self._history.append(dep)
                self._current = None
                return dep

            dep.logs.append(f"Metrics healthy at {pct}%")
            dep.state = CanaryState.RAMPING

        # fully promoted
        dep.state = CanaryState.PROMOTED
        dep.finished_at = time.time()
        dep.logs.append(f"Canary {version} fully promoted to 100%")
        self._history.append(dep)
        self._current = None
        return dep

    def rollback(self) -> Optional[CanaryDeployment]:
        """Manually rollback the current canary deployment."""
        if self._current is None:
            return None
        return self._do_rollback(self._current, "Manual rollback requested")

    def status(self) -> dict[str, Any]:
        """Return current canary status."""
        if self._current:
            return {
                "state": self._current.state.value,
                "version": self._current.version,
                "canary_pct": self._current.traffic.canary_pct,
                "steps": f"{self._current.steps_completed}/{self._current.total_steps}",
            }
        return {"state": "idle", "version": "", "canary_pct": 0.0, "steps": "0/0"}

    # -- internals ----------------------------------------------------------

    def _is_healthy(self, metrics: CanaryMetrics) -> bool:
        if metrics.error_rate > self._config.error_rate_threshold:
            return False
        if metrics.latency_p99_ms > self._config.latency_threshold_ms:
            return False
        return metrics.healthy

    def _do_rollback(self, dep: CanaryDeployment, reason: str) -> CanaryDeployment:
        dep.state = CanaryState.ROLLING_BACK
        dep.logs.append(f"Rolling back: {reason}")
        try:
            self._rollback_fn(dep.version)
        except Exception as exc:  # noqa: BLE001
            dep.logs.append(f"Rollback error: {exc}")
        dep.state = CanaryState.ROLLED_BACK
        dep.traffic = TrafficSplit(canary_pct=0.0)
        dep.error = reason
        dep.finished_at = time.time()
        self._history.append(dep)
        self._current = None
        return dep

    @staticmethod
    def _default_deploy(_version: str, _pct: float) -> bool:
        return True

    @staticmethod
    def _default_metrics(_version: str) -> CanaryMetrics:
        return CanaryMetrics(healthy=True)

    @staticmethod
    def _default_rollback(_version: str) -> bool:
        return True
