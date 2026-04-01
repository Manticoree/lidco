"""Job scheduler with persistence."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from lidco.cron.parser import CronParser


class JobStatus(str, Enum):
    """Status of a scheduled job."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ScheduledJob:
    """A scheduled cron job."""

    id: str
    name: str
    expression: str
    status: JobStatus = JobStatus.ACTIVE
    last_run: float | None = None
    next_run: float | None = None
    run_count: int = 0
    max_runs: int | None = None
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class CronScheduler:
    """Manage scheduled cron jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}
        self._parser = CronParser()

    def add_job(
        self,
        name: str,
        expression: str,
        max_runs: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ScheduledJob:
        """Add a new scheduled job."""
        # Validate expression
        self._parser.parse(expression)
        job_id = uuid.uuid4().hex[:12]
        now = time.time()
        parsed = self._parser.parse(expression)
        next_dt = parsed.next_run(datetime.fromtimestamp(now))
        job = ScheduledJob(
            id=job_id,
            name=name,
            expression=expression,
            status=JobStatus.ACTIVE,
            next_run=next_dt.timestamp(),
            max_runs=max_runs,
            created_at=now,
            metadata=metadata or {},
        )
        self._jobs[job_id] = job
        return job

    def remove_job(self, job_id: str) -> bool:
        """Remove a job. Returns True if found and removed."""
        return self._jobs.pop(job_id, None) is not None

    def get_job(self, job_id: str) -> ScheduledJob | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self, status: JobStatus | None = None) -> list[ScheduledJob]:
        """List all jobs, optionally filtered by status."""
        jobs = list(self._jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return jobs

    def pause_job(self, job_id: str) -> ScheduledJob:
        """Pause an active job."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job '{job_id}' not found")
        updated = ScheduledJob(
            id=job.id,
            name=job.name,
            expression=job.expression,
            status=JobStatus.PAUSED,
            last_run=job.last_run,
            next_run=job.next_run,
            run_count=job.run_count,
            max_runs=job.max_runs,
            created_at=job.created_at,
            metadata=job.metadata,
        )
        self._jobs[job_id] = updated
        return updated

    def resume_job(self, job_id: str) -> ScheduledJob:
        """Resume a paused job."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job '{job_id}' not found")
        parsed = self._parser.parse(job.expression)
        next_dt = parsed.next_run(datetime.now())
        updated = ScheduledJob(
            id=job.id,
            name=job.name,
            expression=job.expression,
            status=JobStatus.ACTIVE,
            last_run=job.last_run,
            next_run=next_dt.timestamp(),
            run_count=job.run_count,
            max_runs=job.max_runs,
            created_at=job.created_at,
            metadata=job.metadata,
        )
        self._jobs[job_id] = updated
        return updated

    def get_due_jobs(self, now: datetime | None = None) -> list[ScheduledJob]:
        """Return all active jobs that are due to run."""
        if now is None:
            now = datetime.now()
        now_ts = now.timestamp()
        due: list[ScheduledJob] = []
        for job in self._jobs.values():
            if job.status != JobStatus.ACTIVE:
                continue
            if job.next_run is not None and job.next_run <= now_ts:
                due.append(job)
        return due

    def mark_run(self, job_id: str, success: bool = True) -> ScheduledJob:
        """Record that a job has been executed."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job '{job_id}' not found")
        now = time.time()
        new_count = job.run_count + 1
        # Determine new status
        if not success:
            new_status = JobStatus.FAILED
        elif job.max_runs is not None and new_count >= job.max_runs:
            new_status = JobStatus.COMPLETED
        else:
            new_status = JobStatus.ACTIVE
        # Compute next_run
        parsed = self._parser.parse(job.expression)
        next_dt = parsed.next_run(datetime.fromtimestamp(now))
        updated = ScheduledJob(
            id=job.id,
            name=job.name,
            expression=job.expression,
            status=new_status,
            last_run=now,
            next_run=next_dt.timestamp() if new_status == JobStatus.ACTIVE else None,
            run_count=new_count,
            max_runs=job.max_runs,
            created_at=job.created_at,
            metadata=job.metadata,
        )
        self._jobs[job_id] = updated
        return updated

    def job_count(self) -> int:
        """Return total number of jobs."""
        return len(self._jobs)
