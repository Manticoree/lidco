"""Unified CI/CD pipeline management across providers."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class PipelineProvider(str, Enum):
    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    CIRCLECI = "circleci"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class PipelineRun:
    id: str
    provider: PipelineProvider
    status: PipelineStatus
    started_at: float = field(default_factory=time.time)
    duration: float = 0.0
    url: str = ""
    branch: str = "main"


_counter: int = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"run_{_counter}"


class PipelineManager:
    """Unified CI/CD pipeline management."""

    def __init__(self) -> None:
        self._runs: list[PipelineRun] = []
        self._providers: dict[str, PipelineProvider] = {}

    def register_provider(self, name: str, provider: PipelineProvider) -> None:
        """Register a named CI/CD provider."""
        self._providers = {**self._providers, name: provider}

    def trigger_build(
        self, provider: PipelineProvider, branch: str = "main"
    ) -> PipelineRun:
        """Trigger a new pipeline build."""
        run = PipelineRun(
            id=_next_id(),
            provider=provider,
            status=PipelineStatus.PENDING,
            branch=branch,
        )
        self._runs = [*self._runs, run]
        return run

    def get_status(self, run_id: str) -> PipelineRun | None:
        """Get status of a pipeline run by ID."""
        for run in self._runs:
            if run.id == run_id:
                return run
        return None

    def list_runs(
        self, provider: PipelineProvider | None = None, limit: int = 20
    ) -> list[PipelineRun]:
        """List pipeline runs, optionally filtered by provider."""
        runs = self._runs
        if provider is not None:
            runs = [r for r in runs if r.provider == provider]
        return runs[-limit:]

    def cancel_run(self, run_id: str) -> bool:
        """Cancel a pipeline run. Returns True if found and cancelled."""
        for i, run in enumerate(self._runs):
            if run.id == run_id:
                cancelled = PipelineRun(
                    id=run.id,
                    provider=run.provider,
                    status=PipelineStatus.CANCELLED,
                    started_at=run.started_at,
                    duration=run.duration,
                    url=run.url,
                    branch=run.branch,
                )
                self._runs = [*self._runs[:i], cancelled, *self._runs[i + 1 :]]
                return True
        return False

    def get_latest(
        self, provider: PipelineProvider | None = None
    ) -> PipelineRun | None:
        """Get the most recent pipeline run."""
        runs = self.list_runs(provider=provider)
        return runs[-1] if runs else None

    def summary(self) -> str:
        """Return human-readable summary."""
        if not self._runs:
            return "No pipeline runs."
        parts = [f"Pipeline runs: {len(self._runs)}"]
        for run in self._runs[-10:]:
            parts.append(
                f"  - {run.id} [{run.provider.value}] {run.status.value} on {run.branch}"
            )
        return "\n".join(parts)
