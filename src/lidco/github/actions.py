"""ActionsMonitor — monitor GitHub Actions CI runs (simulated)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Run:
    """A single CI run."""

    id: int
    repo: str
    status: str  # queued | in_progress | completed
    conclusion: str | None = None  # success | failure | cancelled | None
    logs: list[str] = field(default_factory=list)


class ActionsMonitor:
    """Simulated GitHub Actions monitor."""

    def __init__(self) -> None:
        self._runs: dict[int, Run] = {}
        self._next_id: int = 1

    # -- internal helpers for testing ------------------------------------

    def _add_run(self, repo: str, status: str = "completed",
                 conclusion: str | None = "success",
                 logs: list[str] | None = None) -> Run:
        run = Run(
            id=self._next_id,
            repo=repo,
            status=status,
            conclusion=conclusion,
            logs=logs or [],
        )
        self._runs[run.id] = run
        self._next_id += 1
        return run

    # -- public API ------------------------------------------------------

    def list_runs(self, repo: str) -> list[Run]:
        """List all runs for *repo*."""
        if not repo:
            raise ValueError("repo is required")
        return [r for r in self._runs.values() if r.repo == repo]

    def get_run(self, run_id: int) -> Run | None:
        """Get a specific run by id."""
        return self._runs.get(run_id)

    def parse_logs(self, run_id: int) -> list[str]:
        """Return parsed log lines for a run."""
        run = self._runs.get(run_id)
        if run is None:
            return []
        return [line.strip() for line in run.logs if line.strip()]

    def detect_failures(self, run_id: int) -> list[str]:
        """Return lines that look like failures from a run's logs."""
        run = self._runs.get(run_id)
        if run is None:
            return []
        keywords = ("error", "fail", "exception", "fatal")
        return [
            line for line in run.logs
            if any(kw in line.lower() for kw in keywords)
        ]

    def retrigger(self, run_id: int) -> bool:
        """Re-trigger a run. Returns True on success."""
        run = self._runs.get(run_id)
        if run is None:
            return False
        run.status = "queued"
        run.conclusion = None
        return True
