"""JobQueue — priority job execution with worker threads (stdlib only)."""
from __future__ import annotations

import enum
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable


class JobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobResult:
    job_id: str
    result: object
    error: str
    elapsed_ms: float


@dataclass
class Job:
    id: str
    name: str
    fn: Callable
    args: tuple
    kwargs: dict
    priority: int = 0
    status: JobStatus = JobStatus.PENDING
    result: JobResult | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex

    def __lt__(self, other: "Job") -> bool:
        """Lower priority number = higher priority in PriorityQueue."""
        return self.priority < other.priority


_SENTINEL = object()


class JobQueue:
    """Priority job queue backed by worker threads."""

    def __init__(self) -> None:
        self._pq: queue.PriorityQueue = queue.PriorityQueue()
        self._jobs: dict[str, Job] = {}
        self._workers: list[threading.Thread] = []
        self._running = False
        self._lock = threading.Lock()

    def submit(self, name: str, fn: Callable, *args, priority: int = 0, **kwargs) -> Job:
        """Create and enqueue a job.  Return the Job."""
        job = Job(
            id=uuid.uuid4().hex,
            name=name,
            fn=fn,
            args=args,
            kwargs=kwargs,
            priority=priority,
        )
        with self._lock:
            self._jobs = {**self._jobs, job.id: job}
        self._pq.put((priority, job))
        return job

    def start(self, workers: int = 2) -> None:
        """Start worker threads.  Idempotent if already running."""
        if self._running:
            return
        self._running = True
        self._workers = []
        for _ in range(workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            self._workers.append(t)

    def stop(self, wait: bool = True, timeout: float = 5.0) -> None:
        """Signal workers to stop.  If *wait*, join threads."""
        self._running = False
        # Send sentinels to unblock workers waiting on get()
        for _ in self._workers:
            self._pq.put((0, _SENTINEL))
        if wait:
            for t in self._workers:
                t.join(timeout=timeout)
        self._workers = []

    def list_jobs(self, status: JobStatus | None = None) -> list[Job]:
        """Return all jobs, optionally filtered by status."""
        with self._lock:
            jobs = list(self._jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at)

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        """Cancel a PENDING job.  Returns True if cancelled."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != JobStatus.PENDING:
                return False
            updated = Job(
                id=job.id, name=job.name, fn=job.fn,
                args=job.args, kwargs=job.kwargs,
                priority=job.priority,
                status=JobStatus.CANCELLED,
                created_at=job.created_at,
            )
            self._jobs = {**self._jobs, job_id: updated}
            return True

    @property
    def running(self) -> bool:
        return self._running

    @property
    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status == JobStatus.PENDING)

    # ----------------------------------------------------------------- worker

    def _worker(self) -> None:
        while self._running:
            try:
                item = self._pq.get(timeout=0.5)
            except queue.Empty:
                continue

            _, job = item if isinstance(item, tuple) else (0, item)

            if job is _SENTINEL:
                break

            # Check if cancelled before executing
            with self._lock:
                current = self._jobs.get(job.id)
            if current is None or current.status == JobStatus.CANCELLED:
                self._pq.task_done()
                continue

            # Mark running
            with self._lock:
                running_job = Job(
                    id=job.id, name=job.name, fn=job.fn,
                    args=job.args, kwargs=job.kwargs,
                    priority=job.priority,
                    status=JobStatus.RUNNING,
                    created_at=job.created_at,
                    started_at=time.time(),
                )
                self._jobs = {**self._jobs, job.id: running_job}

            started = running_job.started_at or time.time()
            try:
                result_value = job.fn(*job.args, **job.kwargs)
                finished = time.time()
                job_result = JobResult(
                    job_id=job.id,
                    result=result_value,
                    error="",
                    elapsed_ms=(finished - started) * 1000,
                )
                final_status = JobStatus.COMPLETED
            except Exception as exc:  # noqa: BLE001
                finished = time.time()
                job_result = JobResult(
                    job_id=job.id,
                    result=None,
                    error=str(exc),
                    elapsed_ms=(finished - started) * 1000,
                )
                final_status = JobStatus.FAILED

            with self._lock:
                done_job = Job(
                    id=job.id, name=job.name, fn=job.fn,
                    args=job.args, kwargs=job.kwargs,
                    priority=job.priority,
                    status=final_status,
                    result=job_result,
                    created_at=job.created_at,
                    started_at=started,
                    finished_at=finished,
                )
                self._jobs = {**self._jobs, job.id: done_job}

            self._pq.task_done()
