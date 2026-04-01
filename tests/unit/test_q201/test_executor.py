"""Tests for lidco.cron.executor."""

from __future__ import annotations

import pytest

from lidco.cron.executor import CronExecutor, JobResult
from lidco.cron.scheduler import JobStatus, ScheduledJob


def _make_job(job_id: str = "j1", name: str = "test") -> ScheduledJob:
    return ScheduledJob(id=job_id, name=name, expression="* * * * *", created_at=0.0)


class TestCronExecutor:
    def test_execute_success(self) -> None:
        executor = CronExecutor()
        job = _make_job()
        result = executor.execute(job, lambda: "ok")
        assert result.success
        assert result.output == "ok"
        assert result.job_id == "j1"
        assert result.duration_ms >= 0

    def test_execute_failure(self) -> None:
        executor = CronExecutor()
        job = _make_job()

        def fail():
            raise ValueError("boom")

        result = executor.execute(job, fail)
        assert not result.success
        assert "boom" in result.error

    def test_execute_none_output(self) -> None:
        executor = CronExecutor()
        job = _make_job()
        result = executor.execute(job, lambda: None)
        assert result.success
        assert result.output == ""

    def test_retry_succeeds_on_second(self) -> None:
        executor = CronExecutor(max_retries=3)
        job = _make_job()
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("transient")
            return "recovered"

        result = executor.execute_with_retry(job, flaky)
        assert result.success
        assert result.output == "recovered"

    def test_retry_all_fail(self) -> None:
        executor = CronExecutor(max_retries=2)
        job = _make_job()

        def always_fail():
            raise RuntimeError("permanent")

        result = executor.execute_with_retry(job, always_fail)
        assert not result.success
        # Should have 2 entries in history (2 retries)
        assert len(executor.history()) == 2

    def test_history_filtered(self) -> None:
        executor = CronExecutor()
        j1 = _make_job("j1")
        j2 = _make_job("j2", "other")
        executor.execute(j1, lambda: "a")
        executor.execute(j2, lambda: "b")
        assert len(executor.history("j1")) == 1
        assert len(executor.history("j2")) == 1
        assert len(executor.history()) == 2

    def test_clear_history(self) -> None:
        executor = CronExecutor()
        job = _make_job()
        executor.execute(job, lambda: "x")
        executor.execute(job, lambda: "y")
        cleared = executor.clear_history()
        assert cleared == 2
        assert len(executor.history()) == 0

    def test_duration_tracking(self) -> None:
        executor = CronExecutor()
        job = _make_job()
        result = executor.execute(job, lambda: "fast")
        assert result.duration_ms >= 0
        assert result.timestamp > 0
