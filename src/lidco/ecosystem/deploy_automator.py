"""Deployment automation to various platforms."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeployTarget(str, Enum):
    VERCEL = "vercel"
    NETLIFY = "netlify"
    FLY_IO = "fly_io"
    RAILWAY = "railway"
    CUSTOM = "custom"


class DeployStatus(str, Enum):
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    LIVE = "live"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class Environment:
    name: str
    target: DeployTarget
    url: str = ""
    variables: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Deployment:
    id: str
    environment: str
    target: DeployTarget
    status: DeployStatus = DeployStatus.PENDING
    started_at: float = field(default_factory=time.time)
    url: str = ""
    commit: str = ""


_counter: int = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"deploy_{_counter}"


class DeployAutomator:
    """Deployment automation to various platforms."""

    def __init__(self) -> None:
        self._environments: dict[str, Environment] = {}
        self._deployments: list[Deployment] = []

    def add_environment(
        self,
        name: str,
        target: DeployTarget,
        url: str = "",
        variables: tuple[tuple[str, str], ...] = (),
    ) -> Environment:
        """Register a deployment environment."""
        env = Environment(name=name, target=target, url=url, variables=variables)
        self._environments = {**self._environments, name: env}
        return env

    def deploy(self, env_name: str, commit: str = "HEAD") -> Deployment | None:
        """Deploy to a named environment. Returns None if env not found."""
        env = self._environments.get(env_name)
        if env is None:
            return None
        deployment = Deployment(
            id=_next_id(),
            environment=env_name,
            target=env.target,
            status=DeployStatus.PENDING,
            url=env.url,
            commit=commit,
        )
        self._deployments = [*self._deployments, deployment]
        return deployment

    def rollback(self, deployment_id: str) -> Deployment | None:
        """Rollback a deployment. Returns new Deployment with ROLLED_BACK status."""
        for dep in self._deployments:
            if dep.id == deployment_id:
                rolled_back = Deployment(
                    id=_next_id(),
                    environment=dep.environment,
                    target=dep.target,
                    status=DeployStatus.ROLLED_BACK,
                    url=dep.url,
                    commit=dep.commit,
                )
                self._deployments = [*self._deployments, rolled_back]
                return rolled_back
        return None

    def get_deployment(self, deployment_id: str) -> Deployment | None:
        """Get a deployment by ID."""
        for dep in self._deployments:
            if dep.id == deployment_id:
                return dep
        return None

    def list_deployments(
        self, env_name: str | None = None, limit: int = 20
    ) -> list[Deployment]:
        """List deployments, optionally filtered by environment."""
        deps = self._deployments
        if env_name is not None:
            deps = [d for d in deps if d.environment == env_name]
        return deps[-limit:]

    def health_check(self, env_name: str) -> dict[str, Any]:
        """Check health of an environment."""
        env = self._environments.get(env_name)
        if env is None:
            return {"env": env_name, "status": "unknown", "url": ""}
        return {"env": env_name, "status": "healthy", "url": env.url}

    def summary(self) -> str:
        """Return human-readable summary."""
        if not self._deployments:
            return "No deployments."
        parts = [f"Deployments: {len(self._deployments)}"]
        for dep in self._deployments[-10:]:
            parts.append(
                f"  - {dep.id} -> {dep.environment} [{dep.target.value}] {dep.status.value}"
            )
        return "\n".join(parts)
