"""JobRecovery — detect interrupted jobs on startup, resume or mark failed (Q225)."""
from __future__ import annotations

import time
from dataclasses import dataclass

from lidco.jobs.persistence import JobPersistenceStore


@dataclass(frozen=True)
class RecoveryAction:
    """Describes what to do with an interrupted job."""

    job_id: str
    action: str  # "resume" / "fail" / "skip"
    reason: str


class JobRecovery:
    """Scan for interrupted (still 'running') jobs and decide recovery actions."""

    def __init__(
        self,
        store: JobPersistenceStore,
        max_resume_age: float = 3600.0,
    ) -> None:
        self._store = store
        self._max_resume_age = max_resume_age

    def scan(self) -> list[RecoveryAction]:
        """Find running jobs and produce recovery actions.

        Jobs younger than *max_resume_age* seconds are marked for resume;
        older ones are marked for fail.
        """
        running = self._store.query(status="running", limit=10000)
        now = time.time()
        actions: list[RecoveryAction] = []
        for job in running:
            age = now - job.updated_at
            if age <= self._max_resume_age:
                actions.append(
                    RecoveryAction(
                        job_id=job.id,
                        action="resume",
                        reason=f"age {age:.0f}s <= max {self._max_resume_age:.0f}s",
                    )
                )
            else:
                actions.append(
                    RecoveryAction(
                        job_id=job.id,
                        action="fail",
                        reason=f"age {age:.0f}s > max {self._max_resume_age:.0f}s",
                    )
                )
        return actions

    def execute(self, actions: list[RecoveryAction] | None = None) -> dict:
        """Apply recovery actions. Returns summary with counts."""
        if actions is None:
            actions = self.scan()
        resumed = 0
        failed = 0
        skipped = 0
        for act in actions:
            if act.action == "resume":
                self._store.update_status(act.job_id, "pending")
                resumed += 1
            elif act.action == "fail":
                self._store.update_status(act.job_id, "failed", error="interrupted")
                failed += 1
            else:
                skipped += 1
        return {"resumed": resumed, "failed": failed, "skipped": skipped}

    def mark_interrupted(self, job_id: str) -> bool:
        """Mark a running job as failed with 'interrupted' error."""
        job = self._store.get(job_id)
        if job is None or job.status != "running":
            return False
        self._store.update_status(job_id, "failed", error="interrupted")
        return True
