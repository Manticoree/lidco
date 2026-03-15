"""Tests for Q42 — BatchProcessor and BestOfN (Tasks 288, 290)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.tdd.batch import BatchJob, BatchProcessor, BatchUnit
from lidco.tdd.best_of_n import Attempt, BestOfN, BestOfNResult


@pytest.fixture()
def mock_session():
    session = MagicMock()
    resp = MagicMock()
    resp.content = "1. Sub-task one\n2. Sub-task two\n3. Sub-task three"
    session.orchestrator.handle = AsyncMock(return_value=resp)
    return session


# ── BatchJob ─────────────────────────────────────────────────────────────────

class TestBatchJob:
    def test_n_done_counts_done(self):
        job = BatchJob(original_task="x")
        job.units = [BatchUnit(1, "t1", status="done"), BatchUnit(2, "t2", status="running")]
        assert job.n_done == 1

    def test_n_failed_counts_failed(self):
        job = BatchJob(original_task="x")
        job.units = [BatchUnit(1, "t1", status="failed"), BatchUnit(2, "t2", status="done")]
        assert job.n_failed == 1

    def test_complete_when_all_finished(self):
        job = BatchJob(original_task="x")
        job.units = [BatchUnit(1, "t", status="done"), BatchUnit(2, "t", status="failed")]
        assert job.complete is True

    def test_not_complete_when_running(self):
        job = BatchJob(original_task="x")
        job.units = [BatchUnit(1, "t", status="running")]
        assert job.complete is False

    def test_summary_contains_task(self):
        job = BatchJob(original_task="big task")
        job.units = [BatchUnit(1, "sub", status="done")]
        assert "big task" in job.summary()


# ── BatchProcessor ────────────────────────────────────────────────────────────

class TestBatchProcessor:
    def test_decompose_parses_numbered_list(self, mock_session):
        async def run():
            proc = BatchProcessor(mock_session)
            units = await proc.decompose("do a big thing", n=3)
            return units
        units = asyncio.run(run())
        assert len(units) == 3
        assert "Sub-task one" in units[0]

    def test_decompose_fallback_on_error(self):
        session = MagicMock()
        session.orchestrator.handle = AsyncMock(side_effect=RuntimeError("down"))
        async def run():
            proc = BatchProcessor(session)
            return await proc.decompose("task")
        units = asyncio.run(run())
        assert units == ["task"]

    def test_run_executes_all_units(self, mock_session):
        # Mock handle to return execution results after decomposition
        call_count = [0]
        responses = ["1. a\n2. b\n3. c", "result a", "result b", "result c"]
        async def mock_handle(*a, **kw):
            resp = MagicMock()
            idx = min(call_count[0], len(responses) - 1)
            resp.content = responses[idx]
            call_count[0] += 1
            return resp
        mock_session.orchestrator.handle = mock_handle

        async def run():
            proc = BatchProcessor(mock_session, n_units=3)
            return await proc.run("big task")
        job = asyncio.run(run())
        assert job.complete
        assert len(job.units) >= 1

    def test_run_marks_failed_unit_on_error(self):
        session = MagicMock()
        call_count = [0]
        async def handle(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call = decompose
                resp = MagicMock()
                resp.content = "1. do thing"
                return resp
            raise RuntimeError("agent failed")
        session.orchestrator.handle = handle

        async def run():
            proc = BatchProcessor(session, n_units=1)
            return await proc.run("task")
        job = asyncio.run(run())
        assert job.n_failed >= 1

    def test_status_callback_fired(self, mock_session):
        events = []
        call_count = [0]
        async def handle(*a, **kw):
            call_count[0] += 1
            resp = MagicMock()
            resp.content = "1. unit one" if call_count[0] == 1 else "done"
            return resp
        mock_session.orchestrator.handle = handle

        async def run():
            proc = BatchProcessor(mock_session, n_units=1)
            return await proc.run("task", status_callback=lambda i, s, m: events.append((i, s)))
        asyncio.run(run())
        assert any(s == "decomposed" for _, s in events)


# ── BestOfN ──────────────────────────────────────────────────────────────────

class TestAttemptScore:
    def test_score_positive_on_all_passed(self):
        from lidco.tdd.runner import TestRunResult
        a = Attempt(index=1, code="x")
        a.test_result = TestRunResult(passed=True, n_passed=5, n_failed=0)
        assert a.score == 5

    def test_score_negative_on_failures(self):
        from lidco.tdd.runner import TestRunResult
        a = Attempt(index=1, code="x")
        a.test_result = TestRunResult(passed=False, n_passed=1, n_failed=2)
        assert a.score == 1 - 4  # 1 passed - 2*2 failed

    def test_score_minus_one_without_tests(self):
        a = Attempt(index=1, code="x")
        assert a.score == -1


class TestBestOfN:
    def test_run_produces_n_attempts(self):
        session = MagicMock()
        call_count = [0]
        async def handle(*a, **kw):
            call_count[0] += 1
            resp = MagicMock()
            resp.content = f"def solution_{call_count[0]}(): pass"
            return resp
        session.orchestrator.handle = handle

        async def run():
            bon = BestOfN(session, n=3)
            return await bon.run("implement foo")
        result = asyncio.run(run())
        assert len(result.attempts) == 3

    def test_best_index_set(self):
        session = MagicMock()
        async def handle(*a, **kw):
            resp = MagicMock()
            resp.content = "code"
            return resp
        session.orchestrator.handle = handle

        async def run():
            bon = BestOfN(session, n=2)
            return await bon.run("task")
        result = asyncio.run(run())
        assert result.best_index in (1, 2)

    def test_best_code_returns_string(self):
        session = MagicMock()
        async def handle(*a, **kw):
            resp = MagicMock()
            resp.content = "print('hello')"
            return resp
        session.orchestrator.handle = handle

        async def run():
            bon = BestOfN(session, n=1)
            return await bon.run("task")
        result = asyncio.run(run())
        assert isinstance(result.best_code, str)

    def test_summary_contains_task(self):
        result = BestOfNResult(task="my task", n=2)
        assert "my task" in result.summary()
