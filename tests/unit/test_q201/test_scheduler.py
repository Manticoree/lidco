"""Tests for lidco.cron.scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from lidco.cron.scheduler import CronScheduler, JobStatus, ScheduledJob


@pytest.fixture
def scheduler() -> CronScheduler:
    return CronScheduler()


class TestCronScheduler:
    def test_add_job(self, scheduler: CronScheduler) -> None:
        job = scheduler.add_job("test-job", "*/5 * * * *")
        assert job.name == "test-job"
        assert job.status == JobStatus.ACTIVE
        assert job.expression == "*/5 * * * *"
        assert job.run_count == 0

    def test_remove_job(self, scheduler: CronScheduler) -> None:
        job = scheduler.add_job("test-job", "0 * * * *")
        assert scheduler.remove_job(job.id)
        assert scheduler.get_job(job.id) is None

    def test_remove_nonexistent(self, scheduler: CronScheduler) -> None:
        assert not scheduler.remove_job("nonexistent")

    def test_get_job(self, scheduler: CronScheduler) -> None:
        job = scheduler.add_job("test-job", "0 * * * *")
        fetched = scheduler.get_job(job.id)
        assert fetched is not None
        assert fetched.name == "test-job"

    def test_list_jobs(self, scheduler: CronScheduler) -> None:
        scheduler.add_job("a", "0 * * * *")
        scheduler.add_job("b", "30 * * * *")
        assert len(scheduler.list_jobs()) == 2

    def test_list_jobs_with_filter(self, scheduler: CronScheduler) -> None:
        j = scheduler.add_job("a", "0 * * * *")
        scheduler.pause_job(j.id)
        scheduler.add_job("b", "30 * * * *")
        assert len(scheduler.list_jobs(status=JobStatus.PAUSED)) == 1
        assert len(scheduler.list_jobs(status=JobStatus.ACTIVE)) == 1

    def test_pause_resume(self, scheduler: CronScheduler) -> None:
        job = scheduler.add_job("a", "0 * * * *")
        paused = scheduler.pause_job(job.id)
        assert paused.status == JobStatus.PAUSED
        resumed = scheduler.resume_job(job.id)
        assert resumed.status == JobStatus.ACTIVE

    def test_get_due_jobs(self, scheduler: CronScheduler) -> None:
        job = scheduler.add_job("a", "0 * * * *")
        # Set a future check time well past the next_run
        future = datetime.now() + timedelta(days=1)
        due = scheduler.get_due_jobs(now=future)
        assert len(due) >= 1

    def test_mark_run_success(self, scheduler: CronScheduler) -> None:
        job = scheduler.add_job("a", "0 * * * *")
        updated = scheduler.mark_run(job.id, success=True)
        assert updated.run_count == 1
        assert updated.last_run is not None
        assert updated.status == JobStatus.ACTIVE

    def test_mark_run_max_runs(self, scheduler: CronScheduler) -> None:
        job = scheduler.add_job("a", "0 * * * *", max_runs=1)
        updated = scheduler.mark_run(job.id, success=True)
        assert updated.status == JobStatus.COMPLETED
        assert updated.run_count == 1

    def test_mark_run_failure(self, scheduler: CronScheduler) -> None:
        job = scheduler.add_job("a", "0 * * * *")
        updated = scheduler.mark_run(job.id, success=False)
        assert updated.status == JobStatus.FAILED

    def test_job_count(self, scheduler: CronScheduler) -> None:
        assert scheduler.job_count() == 0
        scheduler.add_job("a", "0 * * * *")
        scheduler.add_job("b", "30 * * * *")
        assert scheduler.job_count() == 2

    def test_add_job_with_metadata(self, scheduler: CronScheduler) -> None:
        job = scheduler.add_job("a", "0 * * * *", metadata={"env": "prod"})
        assert job.metadata == {"env": "prod"}
