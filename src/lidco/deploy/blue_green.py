"""BlueGreenDeployer — blue-green deployment with traffic switching, health validation,
instant rollback, and zero downtime (stdlib only)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class SlotColor(str, Enum):
    """Active deployment slot."""

    BLUE = "blue"
    GREEN = "green"


class DeploymentState(str, Enum):
    """Lifecycle states for a blue-green deployment."""

    IDLE = "idle"
    DEPLOYING = "deploying"
    VALIDATING = "validating"
    SWITCHING = "switching"
    LIVE = "live"
    ROLLING_BACK = "rolling_back"
    FAILED = "failed"


@dataclass(frozen=True)
class HealthCheckResult:
    """Outcome of a single health check."""

    healthy: bool
    latency_ms: float = 0.0
    detail: str = ""


@dataclass
class SlotInfo:
    """Metadata for one deployment slot."""

    color: SlotColor
    version: str = ""
    healthy: bool = False
    deployed_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BlueGreenDeployment:
    """Record of a blue-green deployment attempt."""

    deployment_id: str = ""
    version: str = ""
    active_slot: SlotColor = SlotColor.BLUE
    inactive_slot: SlotColor = SlotColor.GREEN
    state: DeploymentState = DeploymentState.IDLE
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""
    logs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.deployment_id:
            self.deployment_id = uuid.uuid4().hex

    @property
    def duration_ms(self) -> float:
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at) * 1000
        return 0.0


class BlueGreenDeployer:
    """Manages blue-green deployments with zero-downtime traffic switching."""

    def __init__(
        self,
        health_check: Optional[Callable[[SlotColor], HealthCheckResult]] = None,
        deploy_fn: Optional[Callable[[SlotColor, str], bool]] = None,
        switch_fn: Optional[Callable[[SlotColor], bool]] = None,
        health_retries: int = 3,
        health_interval_s: float = 1.0,
    ) -> None:
        self._health_check = health_check or self._default_health_check
        self._deploy_fn = deploy_fn or self._default_deploy
        self._switch_fn = switch_fn or self._default_switch
        self._health_retries = max(1, health_retries)
        self._health_interval_s = health_interval_s
        self._active_slot = SlotColor.BLUE
        self._slots: dict[SlotColor, SlotInfo] = {
            SlotColor.BLUE: SlotInfo(color=SlotColor.BLUE),
            SlotColor.GREEN: SlotInfo(color=SlotColor.GREEN),
        }
        self._history: list[BlueGreenDeployment] = []

    # -- public properties --------------------------------------------------

    @property
    def active_slot(self) -> SlotColor:
        return self._active_slot

    @property
    def inactive_slot(self) -> SlotColor:
        return SlotColor.GREEN if self._active_slot == SlotColor.BLUE else SlotColor.BLUE

    @property
    def slots(self) -> dict[SlotColor, SlotInfo]:
        return dict(self._slots)

    @property
    def history(self) -> list[BlueGreenDeployment]:
        return list(self._history)

    # -- deploy -------------------------------------------------------------

    def deploy(self, version: str, metadata: Optional[dict[str, Any]] = None) -> BlueGreenDeployment:
        """Deploy *version* to the inactive slot, validate, and switch traffic."""
        target = self.inactive_slot
        dep = BlueGreenDeployment(
            version=version,
            active_slot=self._active_slot,
            inactive_slot=target,
            state=DeploymentState.DEPLOYING,
            started_at=time.time(),
        )
        dep.logs.append(f"Deploying {version} to {target.value} slot")

        # 1. deploy to inactive slot
        try:
            ok = self._deploy_fn(target, version)
        except Exception as exc:  # noqa: BLE001
            dep.state = DeploymentState.FAILED
            dep.error = str(exc)
            dep.finished_at = time.time()
            dep.logs.append(f"Deploy failed: {exc}")
            self._history.append(dep)
            return dep

        if not ok:
            dep.state = DeploymentState.FAILED
            dep.error = "deploy_fn returned False"
            dep.finished_at = time.time()
            dep.logs.append("Deploy function returned failure")
            self._history.append(dep)
            return dep

        self._slots[target] = SlotInfo(
            color=target,
            version=version,
            deployed_at=time.time(),
            metadata=metadata or {},
        )
        dep.logs.append(f"Deployed to {target.value}")

        # 2. health validation
        dep.state = DeploymentState.VALIDATING
        dep.logs.append("Running health checks")
        healthy = self._validate_health(target)
        if not healthy:
            dep.state = DeploymentState.FAILED
            dep.error = "Health checks failed"
            dep.finished_at = time.time()
            dep.logs.append("Health validation failed")
            self._history.append(dep)
            return dep

        self._slots[target] = SlotInfo(
            color=target,
            version=version,
            healthy=True,
            deployed_at=self._slots[target].deployed_at,
            metadata=metadata or {},
        )
        dep.logs.append("Health checks passed")

        # 3. switch traffic
        dep.state = DeploymentState.SWITCHING
        dep.logs.append(f"Switching traffic to {target.value}")
        try:
            switched = self._switch_fn(target)
        except Exception as exc:  # noqa: BLE001
            dep.state = DeploymentState.FAILED
            dep.error = f"Switch failed: {exc}"
            dep.finished_at = time.time()
            dep.logs.append(f"Traffic switch failed: {exc}")
            self._history.append(dep)
            return dep

        if not switched:
            dep.state = DeploymentState.FAILED
            dep.error = "switch_fn returned False"
            dep.finished_at = time.time()
            self._history.append(dep)
            return dep

        self._active_slot = target
        dep.state = DeploymentState.LIVE
        dep.finished_at = time.time()
        dep.logs.append(f"Traffic now on {target.value} — deployment live")
        self._history.append(dep)
        return dep

    # -- rollback -----------------------------------------------------------

    def rollback(self) -> BlueGreenDeployment:
        """Instantly switch traffic back to the previous slot."""
        previous = self.inactive_slot
        dep = BlueGreenDeployment(
            version=self._slots[previous].version,
            active_slot=self._active_slot,
            inactive_slot=previous,
            state=DeploymentState.ROLLING_BACK,
            started_at=time.time(),
        )
        dep.logs.append(f"Rolling back to {previous.value} (version {dep.version})")

        try:
            switched = self._switch_fn(previous)
        except Exception as exc:  # noqa: BLE001
            dep.state = DeploymentState.FAILED
            dep.error = str(exc)
            dep.finished_at = time.time()
            self._history.append(dep)
            return dep

        if not switched:
            dep.state = DeploymentState.FAILED
            dep.error = "switch_fn returned False during rollback"
            dep.finished_at = time.time()
            self._history.append(dep)
            return dep

        self._active_slot = previous
        dep.state = DeploymentState.LIVE
        dep.finished_at = time.time()
        dep.logs.append(f"Rollback complete — traffic on {previous.value}")
        self._history.append(dep)
        return dep

    # -- status -------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return current deployment status."""
        return {
            "active_slot": self._active_slot.value,
            "blue": {
                "version": self._slots[SlotColor.BLUE].version,
                "healthy": self._slots[SlotColor.BLUE].healthy,
            },
            "green": {
                "version": self._slots[SlotColor.GREEN].version,
                "healthy": self._slots[SlotColor.GREEN].healthy,
            },
            "deployments": len(self._history),
        }

    # -- internals ----------------------------------------------------------

    def _validate_health(self, slot: SlotColor) -> bool:
        for attempt in range(self._health_retries):
            result = self._health_check(slot)
            if result.healthy:
                return True
            if attempt < self._health_retries - 1:
                time.sleep(self._health_interval_s)
        return False

    @staticmethod
    def _default_health_check(_slot: SlotColor) -> HealthCheckResult:
        return HealthCheckResult(healthy=True)

    @staticmethod
    def _default_deploy(_slot: SlotColor, _version: str) -> bool:
        return True

    @staticmethod
    def _default_switch(_slot: SlotColor) -> bool:
        return True
