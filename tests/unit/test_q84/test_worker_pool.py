"""Tests for WorkerPool (T554)."""
from __future__ import annotations
import asyncio
import pytest
from lidco.agents.worker_pool import WorkerPool, WorkItem, WorkResult, PoolResult


async def _ok(val: str = "ok") -> str:
    return val


async def _fail() -> str:
    raise ValueError("boom")


async def _slow() -> str:
    await asyncio.sleep(10)
    return "slow"


def test_run_all_success():
    pool = WorkerPool(max_workers=2)
    items = [WorkItem("t1", _ok("a")), WorkItem("t2", _ok("b"))]
    result = asyncio.run(pool.run_all(items))
    assert result.successful == 2
    assert result.failed == 0
    assert result.all_success


def test_run_all_failure():
    pool = WorkerPool(max_workers=2)
    items = [WorkItem("ok", _ok()), WorkItem("bad", _fail())]
    result = asyncio.run(pool.run_all(items))
    assert result.successful == 1
    assert result.failed == 1
    assert not result.all_success


def test_run_all_empty():
    pool = WorkerPool()
    result = asyncio.run(pool.run_all([]))
    assert result.successful == 0
    assert result.failed == 0


def test_timeout():
    pool = WorkerPool(max_workers=1, default_timeout=0.05)
    items = [WorkItem("slow", _slow())]
    result = asyncio.run(pool.run_all(items))
    assert result.successful == 0
    assert "timed out" in result.results[0].error


def test_get_by_name():
    pool = WorkerPool()
    items = [WorkItem("alpha", _ok("x")), WorkItem("beta", _ok("y"))]
    result = asyncio.run(pool.run_all(items))
    r = result.get("alpha")
    assert r is not None
    assert r.result == "x"


def test_submit_one():
    pool = WorkerPool()
    r = asyncio.run(pool.submit_one("t", _ok("hello")))
    assert r.success
    assert r.result == "hello"


def test_run_sync():
    pool = WorkerPool()
    items = [WorkItem("x", _ok("val"))]
    result = pool.run_sync(items)
    assert result.successful == 1


def test_format_summary():
    pool = WorkerPool()
    items = [WorkItem("a", _ok("done")), WorkItem("b", _fail())]
    result = asyncio.run(pool.run_all(items))
    summary = result.format_summary()
    assert "ok" in summary
    assert "failed" in summary
