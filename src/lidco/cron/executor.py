"""Execute cron jobs with output capture and retry."""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from lidco.cron.scheduler import ScheduledJob


@dataclass(frozen=True)
class JobResult:
    """Result of a job execution."""

    job_id: str
    success: bool
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0
    timestamp: float = 0.0


class CronExecutor:
    """Execute cron jobs with retry support."""

    def __init__(self, max_retries: int = 3) -> None:
        self._max_retries = max_retries
        self._history: list[JobResult] = []

    def execute(self, job: ScheduledJob, handler: Callable[..., Any]) -> JobResult:
        """Execute a single job and capture the result."""
        start = time.time()
        try:
            result = handler()
            duration = (time.time() - start) * 1000
            jr = JobResult(
                job_id=job.id,
                success=True,
                output=str(result) if result is not None else "",
                duration_ms=duration,
                timestamp=time.time(),
            )
        except Exception as exc:
            duration = (time.time() - start) * 1000
            jr = JobResult(
                job_id=job.id,
                success=False,
                error=str(exc),
                duration_ms=duration,
                timestamp=time.time(),
            )
        self._history.append(jr)
        return jr

    def execute_with_retry(
        self, job: ScheduledJob, handler: Callable[..., Any]
    ) -> JobResult:
        """Execute a job with up to *max_retries* attempts."""
        last_result: JobResult | None = None
        for attempt in range(self._max_retries):
            result = self.execute(job, handler)
            if result.success:
                return result
            last_result = result
        # All attempts failed — return last failure
        assert last_result is not None
        return last_result

    def history(self, job_id: str | None = None) -> list[JobResult]:
        """Return execution history, optionally filtered by job_id."""
        if job_id is None:
            return list(self._history)
        return [r for r in self._history if r.job_id == job_id]

    def clear_history(self) -> int:
        """Clear execution history. Returns number of entries cleared."""
        count = len(self._history)
        self._history.clear()
        return count
