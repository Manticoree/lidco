"""JobScheduler — priority queue with max-concurrency and dependency awareness (Q225)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from lidco.jobs.persistence import JobPersistenceStore, JobRecord


@dataclass
class ScheduledJob:
    """A job submitted to the scheduler."""

    id: str
    name: str
    priority: int = 0
    depends_on: list[str] = field(default_factory=list)
    payload: str = "{}"


class JobScheduler:
    """Priority-based scheduler with concurrency limits and dependency tracking."""

    def __init__(
        self,
        max_concurrent: int = 4,
        store: JobPersistenceStore | None = None,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._store = store
        self._queue: list[ScheduledJob] = []
        self._running_ids: list[str] = []
        self._completed_ids: set[str] = set()
        self._failed_ids: set[str] = set()
        self._cancelled_ids: set[str] = set()
        self._all: dict[str, ScheduledJob] = {}

    def submit(
        self,
        name: str,
        payload: str = "{}",
        priority: int = 0,
        depends_on: list[str] | None = None,
    ) -> ScheduledJob:
        """Submit a new job to the scheduler."""
        job = ScheduledJob(
            id=uuid.uuid4().hex,
            name=name,
            priority=priority,
            depends_on=list(depends_on) if depends_on else [],
            payload=payload,
        )
        self._all[job.id] = job
        self._queue.append(job)
        if self._store is not None:
            now = time.time()
            self._store.save(JobRecord(
                id=job.id,
                name=job.name,
                status="pending",
                payload=payload,
                result=None,
                created_at=now,
                updated_at=now,
            ))
        return job

    def next(self) -> ScheduledJob | None:
        """Return the next eligible job (deps met, under concurrency limit).

        Higher priority numbers are scheduled first.
        """
        if len(self._running_ids) >= self._max_concurrent:
            return None
        # Sort eligible by priority descending
        eligible: list[ScheduledJob] = []
        for job in self._queue:
            if self._deps_met(job):
                eligible.append(job)
        if not eligible:
            return None
        eligible.sort(key=lambda j: j.priority, reverse=True)
        chosen = eligible[0]
        self._queue.remove(chosen)
        self._running_ids.append(chosen.id)
        if self._store is not None:
            self._store.update_status(chosen.id, "running")
        return chosen

    def complete(self, job_id: str, result: str | None = None) -> bool:
        """Mark a running job as completed."""
        if job_id not in self._running_ids:
            return False
        self._running_ids.remove(job_id)
        self._completed_ids.add(job_id)
        if self._store is not None:
            self._store.update_status(job_id, "completed", result=result)
        return True

    def fail(self, job_id: str, error: str) -> bool:
        """Mark a running job as failed."""
        if job_id not in self._running_ids:
            return False
        self._running_ids.remove(job_id)
        self._failed_ids.add(job_id)
        if self._store is not None:
            self._store.update_status(job_id, "failed", error=error)
        return True

    def cancel(self, job_id: str) -> bool:
        """Cancel a pending job (removes from queue)."""
        for i, job in enumerate(self._queue):
            if job.id == job_id:
                self._queue.pop(i)
                self._cancelled_ids.add(job_id)
                if self._store is not None:
                    self._store.update_status(job_id, "cancelled")
                return True
        return False

    def pending(self) -> list[ScheduledJob]:
        """Return all pending (queued) jobs."""
        return list(self._queue)

    def running(self) -> list[str]:
        """Return IDs of currently running jobs."""
        return list(self._running_ids)

    def is_blocked(self, job_id: str) -> bool:
        """Return True if the job's dependencies are not yet met."""
        job = self._all.get(job_id)
        if job is None:
            return False
        return not self._deps_met(job)

    def summary(self) -> dict:
        """Return scheduler state summary."""
        return {
            "pending": len(self._queue),
            "running": len(self._running_ids),
            "completed": len(self._completed_ids),
            "failed": len(self._failed_ids),
            "cancelled": len(self._cancelled_ids),
            "max_concurrent": self._max_concurrent,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _deps_met(self, job: ScheduledJob) -> bool:
        """Check whether all dependencies of *job* are completed."""
        for dep_id in job.depends_on:
            if dep_id not in self._completed_ids:
                return False
        return True
