"""Tests for WorktreeRunner (T545)."""
from __future__ import annotations
import asyncio
import pytest
from lidco.agents.worktree_runner import WorktreeRunner, WorktreeTask, WorktreeResult, ParallelResult


def test_worktree_task_dataclass():
    t = WorktreeTask(name="test", prompt="do something")
    assert t.name == "test"
    assert t.branch == ""


def test_parallel_result_all_success():
    r1 = WorktreeResult(task=WorktreeTask(name="a", prompt=""), success=True, output="ok", worktree_path="/tmp/a", branch="b1")
    r2 = WorktreeResult(task=WorktreeTask(name="b", prompt=""), success=True, output="ok", worktree_path="/tmp/b", branch="b2")
    pr = ParallelResult(results=[r1, r2], successful=2, failed=0)
    assert pr.all_success is True


def test_parallel_result_not_all_success():
    r1 = WorktreeResult(task=WorktreeTask(name="a", prompt=""), success=True, output="ok", worktree_path="/tmp/a", branch="b1")
    r2 = WorktreeResult(task=WorktreeTask(name="b", prompt=""), success=False, output="", worktree_path="/tmp/b", branch="b2", error="fail")
    pr = ParallelResult(results=[r1, r2], successful=1, failed=1)
    assert pr.all_success is False


def test_make_branch_name(tmp_path):
    runner = WorktreeRunner(tmp_path)
    name = runner._make_branch_name("My Task", 0)
    assert name.startswith("lidco-parallel-0-")
    assert " " not in name


def test_run_parallel_no_runner(tmp_path):
    runner = WorktreeRunner(tmp_path)
    tasks = [WorktreeTask(name="task1", prompt="p1"), WorktreeTask(name="task2", prompt="p2")]
    result = asyncio.run(runner.run_parallel(tasks))
    assert len(result.results) == 2


def test_run_parallel_with_runner(tmp_path):
    async def my_runner(task, wt_path):
        return f"done: {task.name}"

    runner = WorktreeRunner(tmp_path, task_runner=my_runner)
    tasks = [WorktreeTask(name="t1", prompt=""), WorktreeTask(name="t2", prompt="")]
    result = asyncio.run(runner.run_parallel(tasks))
    assert result.successful == 2
    assert "done: t1" in result.results[0].output


def test_run_parallel_runner_raises(tmp_path):
    async def bad_runner(task, wt_path):
        raise ValueError("simulated failure")

    runner = WorktreeRunner(tmp_path, task_runner=bad_runner)
    tasks = [WorktreeTask(name="t1", prompt="")]
    result = asyncio.run(runner.run_parallel(tasks))
    assert result.failed == 1
    assert "simulated failure" in result.results[0].error


def test_run_parallel_empty(tmp_path):
    runner = WorktreeRunner(tmp_path)
    result = asyncio.run(runner.run_parallel([]))
    assert result.successful == 0
    assert result.failed == 0
