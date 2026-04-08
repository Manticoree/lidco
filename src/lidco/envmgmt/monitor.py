"""Env Monitor — monitor environment health.

Resource usage, config drift, expiry tracking, cost per environment.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lidco.envmgmt.provisioner import EnvStatus, Environment


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ResourceUsage:
    """Snapshot of resource usage."""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_in_bytes: int = 0
    network_out_bytes: int = 0


@dataclass(frozen=True)
class CostEstimate:
    """Cost estimate for an environment."""

    hourly: float = 0.0
    daily: float = 0.0
    monthly: float = 0.0
    currency: str = "USD"


@dataclass
class HealthReport:
    """Health report for a single environment."""

    env_id: str
    env_name: str
    status: HealthStatus
    uptime_seconds: float = 0.0
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    cost: CostEstimate = field(default_factory=CostEstimate)
    drift_detected: bool = False
    drift_keys: list[str] = field(default_factory=list)
    expires_in_seconds: float | None = None
    warnings: list[str] = field(default_factory=list)


# Base cost per replica per hour by tier
_TIER_COST_PER_REPLICA: dict[str, float] = {
    "dev": 0.05,
    "staging": 0.15,
    "prod": 0.50,
}


class EnvMonitor:
    """Monitor environment health, resources, drift, expiry, cost."""

    def __init__(self) -> None:
        self._resource_snapshots: dict[str, ResourceUsage] = {}
        self._baselines: dict[str, dict[str, Any]] = {}
        self._expiry_times: dict[str, float] = {}
        self._thresholds = {
            "cpu_warning": 70.0,
            "cpu_critical": 90.0,
            "memory_warning": 75.0,
            "memory_critical": 95.0,
            "disk_warning": 80.0,
            "disk_critical": 95.0,
        }

    # -- Configuration --------------------------------------------------------

    def set_thresholds(self, thresholds: dict[str, float]) -> None:
        self._thresholds.update(thresholds)

    # -- Resource snapshots ---------------------------------------------------

    def record_usage(self, env_id: str, usage: ResourceUsage) -> None:
        self._resource_snapshots[env_id] = usage

    def get_usage(self, env_id: str) -> ResourceUsage | None:
        return self._resource_snapshots.get(env_id)

    # -- Baseline / drift detection -------------------------------------------

    def set_baseline(self, env_id: str, config: dict[str, Any]) -> None:
        self._baselines[env_id] = dict(config)

    def detect_drift(self, env: Environment) -> tuple[bool, list[str]]:
        """Compare current config to baseline. Returns (drifted, keys)."""
        baseline = self._baselines.get(env.env_id)
        if baseline is None:
            return False, []

        drifted_keys: list[str] = []
        all_keys = set(baseline) | set(env.config)
        for key in sorted(all_keys):
            bval = baseline.get(key)
            cval = env.config.get(key)
            if bval != cval:
                drifted_keys.append(key)

        return bool(drifted_keys), drifted_keys

    # -- Expiry tracking ------------------------------------------------------

    def set_expiry(self, env_id: str, expires_at: float) -> None:
        self._expiry_times[env_id] = expires_at

    def time_until_expiry(self, env_id: str) -> float | None:
        expires_at = self._expiry_times.get(env_id)
        if expires_at is None:
            return None
        return max(0.0, expires_at - time.time())

    def get_expired_envs(self, envs: list[Environment]) -> list[Environment]:
        now = time.time()
        expired: list[Environment] = []
        for env in envs:
            exp = self._expiry_times.get(env.env_id)
            if exp is not None and exp <= now and env.status == EnvStatus.ACTIVE:
                expired.append(env)
        return expired

    # -- Cost estimation ------------------------------------------------------

    def estimate_cost(self, env: Environment) -> CostEstimate:
        replicas = env.config.get("replicas", 1)
        rate = _TIER_COST_PER_REPLICA.get(env.tier.value, 0.10)
        hourly = replicas * rate
        return CostEstimate(
            hourly=round(hourly, 4),
            daily=round(hourly * 24, 4),
            monthly=round(hourly * 24 * 30, 4),
        )

    # -- Health check ---------------------------------------------------------

    def check_health(self, env: Environment) -> HealthReport:
        """Full health check for an environment."""
        usage = self._resource_snapshots.get(env.env_id, ResourceUsage())
        drift, drift_keys = self.detect_drift(env)
        cost = self.estimate_cost(env)
        expires_in = self.time_until_expiry(env.env_id)

        warnings: list[str] = []
        status = HealthStatus.HEALTHY

        if env.status != EnvStatus.ACTIVE:
            status = HealthStatus.CRITICAL
            warnings.append(f"Environment status is {env.status.value}")

        # CPU
        if usage.cpu_percent >= self._thresholds["cpu_critical"]:
            status = HealthStatus.CRITICAL
            warnings.append(f"CPU at {usage.cpu_percent}%")
        elif usage.cpu_percent >= self._thresholds["cpu_warning"]:
            if status != HealthStatus.CRITICAL:
                status = HealthStatus.WARNING
            warnings.append(f"CPU at {usage.cpu_percent}%")

        # Memory
        if usage.memory_percent >= self._thresholds["memory_critical"]:
            status = HealthStatus.CRITICAL
            warnings.append(f"Memory at {usage.memory_percent}%")
        elif usage.memory_percent >= self._thresholds["memory_warning"]:
            if status != HealthStatus.CRITICAL:
                status = HealthStatus.WARNING
            warnings.append(f"Memory at {usage.memory_percent}%")

        # Disk
        if usage.disk_percent >= self._thresholds["disk_critical"]:
            status = HealthStatus.CRITICAL
            warnings.append(f"Disk at {usage.disk_percent}%")
        elif usage.disk_percent >= self._thresholds["disk_warning"]:
            if status != HealthStatus.CRITICAL:
                status = HealthStatus.WARNING
            warnings.append(f"Disk at {usage.disk_percent}%")

        # Drift
        if drift:
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.WARNING
            warnings.append(f"Config drift detected: {', '.join(drift_keys)}")

        # Expiry
        if expires_in is not None and expires_in <= 0:
            warnings.append("Environment has expired")
            if status != HealthStatus.CRITICAL:
                status = HealthStatus.WARNING

        now = time.time()
        uptime = now - env.created_at if env.status == EnvStatus.ACTIVE else 0.0

        return HealthReport(
            env_id=env.env_id,
            env_name=env.name,
            status=status,
            uptime_seconds=uptime,
            resource_usage=usage,
            cost=cost,
            drift_detected=drift,
            drift_keys=drift_keys,
            expires_in_seconds=expires_in,
            warnings=warnings,
        )
