"""JobProgress — structured progress tracking for background jobs (Q225)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from lidco.jobs.persistence import JobPersistenceStore


@dataclass
class ProgressUpdate:
    """A single progress snapshot."""

    job_id: str
    percentage: float  # 0–100
    message: str
    substep: str | None = None
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class JobProgress:
    """Track progress updates for background jobs."""

    def __init__(self, store: JobPersistenceStore | None = None) -> None:
        self._store = store
        self._history: dict[str, list[ProgressUpdate]] = {}

    def update(
        self,
        job_id: str,
        percentage: float,
        message: str,
        substep: str | None = None,
    ) -> ProgressUpdate:
        """Record a progress update for *job_id*."""
        pct = max(0.0, min(100.0, percentage))
        pu = ProgressUpdate(
            job_id=job_id,
            percentage=pct,
            message=message,
            substep=substep,
        )
        if job_id not in self._history:
            self._history[job_id] = []
        self._history[job_id].append(pu)
        return pu

    def get(self, job_id: str) -> ProgressUpdate | None:
        """Return the latest progress update for *job_id*."""
        entries = self._history.get(job_id)
        if not entries:
            return None
        return entries[-1]

    def history(self, job_id: str) -> list[ProgressUpdate]:
        """Return the full progress history for *job_id*."""
        return list(self._history.get(job_id, []))

    def is_complete(self, job_id: str) -> bool:
        """Return True if the latest progress is 100%."""
        latest = self.get(job_id)
        if latest is None:
            return False
        return latest.percentage >= 100.0

    def summary(self) -> dict:
        """Return a summary of all active (non-complete) jobs and their progress."""
        result: dict[str, dict] = {}
        for job_id, entries in self._history.items():
            if not entries:
                continue
            latest = entries[-1]
            if latest.percentage < 100.0:
                result[job_id] = {
                    "percentage": latest.percentage,
                    "message": latest.message,
                    "substep": latest.substep,
                }
        return result
