"""Q129 — Metrics & Telemetry: HealthCheck and HealthRegistry."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class HealthStatus:
    name: str
    healthy: bool
    message: str = ""
    details: dict = field(default_factory=dict)


class HealthCheck:
    """A named health check that wraps a callable predicate."""

    def __init__(
        self,
        name: str,
        check_fn: Callable[[], bool],
        description: str = "",
    ) -> None:
        self._name = name
        self._check_fn = check_fn
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def run(self) -> HealthStatus:
        try:
            result = self._check_fn()
            healthy = bool(result)
            message = "OK" if healthy else "Check returned False"
        except Exception as exc:
            healthy = False
            message = f"Exception: {exc}"
        return HealthStatus(name=self._name, healthy=healthy, message=message)


class HealthRegistry:
    """Registry for multiple named health checks."""

    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}

    def register(self, check: HealthCheck) -> None:
        self._checks[check.name] = check

    def run_all(self) -> list[HealthStatus]:
        return [check.run() for check in self._checks.values()]

    def is_healthy(self) -> bool:
        return all(s.healthy for s in self.run_all())

    def summary(self) -> dict:
        statuses = self.run_all()
        healthy = sum(1 for s in statuses if s.healthy)
        unhealthy = sum(1 for s in statuses if not s.healthy)
        return {"healthy": healthy, "unhealthy": unhealthy}

    def names(self) -> list[str]:
        return list(self._checks.keys())
