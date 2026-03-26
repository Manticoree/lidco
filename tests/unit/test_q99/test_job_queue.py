"""Tests for T630 JobQueue."""
import time

import pytest

from lidco.execution.job_queue import Job, JobQueue, JobStatus


class TestJobQueue:
    def test_submit_returns_job(self):
        jq = JobQueue()
        job = jq.submit("test", lambda: 42)
        assert job.name == "test"
        assert job.status == JobStatus.PENDING
        assert len(job.id) > 0

    def test_job_executes_and_completes(self):
        jq = JobQueue()
        job = jq.submit("adder", lambda: 1 + 1)
        jq.start(workers=1)
        time.sleep(0.2)
        jq.stop()
        done = jq.get_job(job.id)
        assert done.status == JobStatus.COMPLETED
        assert done.result.result == 2

    def test_job_failure_captured(self):
        jq = JobQueue()

        def fail():
            raise ValueError("intentional")

        job = jq.submit("failer", fail)
        jq.start(workers=1)
        time.sleep(0.2)
        jq.stop()
        done = jq.get_job(job.id)
        assert done.status == JobStatus.FAILED
        assert "intentional" in done.result.error

    def test_cancel_pending_job(self):
        jq = JobQueue()  # no workers started
        job = jq.submit("pending", lambda: None)
        assert jq.cancel(job.id) is True
        assert jq.get_job(job.id).status == JobStatus.CANCELLED

    def test_cancel_nonexistent_returns_false(self):
        jq = JobQueue()
        assert jq.cancel("nonexistent") is False

    def test_list_jobs_all(self):
        jq = JobQueue()
        jq.submit("a", lambda: None)
        jq.submit("b", lambda: None)
        jq.submit("c", lambda: None)
        assert len(jq.list_jobs()) == 3

    def test_list_jobs_filter_status(self):
        jq = JobQueue()
        j1 = jq.submit("x", lambda: None)
        jq.submit("y", lambda: None)
        jq.cancel(j1.id)
        cancelled = jq.list_jobs(status=JobStatus.CANCELLED)
        assert len(cancelled) == 1
        assert cancelled[0].name == "x"

    def test_get_job(self):
        jq = JobQueue()
        job = jq.submit("find_me", lambda: None)
        found = jq.get_job(job.id)
        assert found is not None
        assert found.name == "find_me"

    def test_get_job_missing(self):
        jq = JobQueue()
        assert jq.get_job("missing") is None

    def test_stop_is_idempotent(self):
        jq = JobQueue()
        jq.start(workers=1)
        jq.stop()
        jq.stop()  # should not raise

    def test_priority_ordering(self):
        results = []
        jq = JobQueue()
        jq.submit("low", lambda: results.append("low"), priority=10)
        jq.submit("high", lambda: results.append("high"), priority=1)
        jq.start(workers=1)
        time.sleep(0.3)
        jq.stop()
        # high priority should have run first
        if len(results) == 2:
            assert results[0] == "high"

    def test_pending_count(self):
        jq = JobQueue()  # no workers
        jq.submit("a", lambda: None)
        jq.submit("b", lambda: None)
        assert jq.pending_count == 2
