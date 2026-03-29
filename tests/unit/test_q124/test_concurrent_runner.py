"""Tests for src/lidco/execution/concurrent_runner.py."""
from __future__ import annotations

import asyncio
import time

import pytest

from lidco.execution.concurrent_runner import (
    ConcurrentRunner,
    RunReport,
    TaskOutcome,
    TaskSpec,
)


# ------------------------------------------------------------------ #
# TaskSpec                                                             #
# ------------------------------------------------------------------ #

class TestTaskSpec:
    def test_fields(self):
        async def fn(): return 1
        spec = TaskSpec(id="abc", name="t1", fn=fn, timeout=5.0)
        assert spec.id == "abc"
        assert spec.name == "t1"
        assert spec.fn is fn
        assert spec.timeout == 5.0

    def test_timeout_defaults_none(self):
        async def fn(): return 1
        spec = TaskSpec(id="x", name="t", fn=fn)
        assert spec.timeout is None


# ------------------------------------------------------------------ #
# TaskOutcome                                                          #
# ------------------------------------------------------------------ #

class TestTaskOutcome:
    def test_defaults(self):
        o = TaskOutcome(id="1", name="t")
        assert o.result is None
        assert o.error == ""
        assert o.success is True
        assert o.elapsed == 0.0

    def test_failure_outcome(self):
        o = TaskOutcome(id="2", name="t", error="boom", success=False)
        assert not o.success
        assert o.error == "boom"


# ------------------------------------------------------------------ #
# RunReport                                                            #
# ------------------------------------------------------------------ #

class TestRunReport:
    def _make_report(self, successes: int, failures: int) -> RunReport:
        outcomes = (
            [TaskOutcome(id=str(i), name=f"t{i}", success=True) for i in range(successes)]
            + [TaskOutcome(id=str(i + 100), name=f"f{i}", success=False) for i in range(failures)]
        )
        return RunReport(outcomes=outcomes, total_elapsed=1.0)

    def test_succeeded(self):
        r = self._make_report(3, 1)
        assert r.succeeded == 3

    def test_failed(self):
        r = self._make_report(3, 1)
        assert r.failed == 1

    def test_success_rate_all(self):
        r = self._make_report(4, 0)
        assert r.success_rate == 1.0

    def test_success_rate_partial(self):
        r = self._make_report(1, 1)
        assert r.success_rate == 0.5

    def test_success_rate_empty(self):
        r = RunReport(outcomes=[], total_elapsed=0.0)
        assert r.success_rate == 0.0

    def test_all_failed(self):
        r = self._make_report(0, 3)
        assert r.succeeded == 0
        assert r.failed == 3
        assert r.success_rate == 0.0


# ------------------------------------------------------------------ #
# ConcurrentRunner                                                     #
# ------------------------------------------------------------------ #

class TestConcurrentRunner:
    def test_run_sync_all_success(self):
        async def fn(): return 42

        runner = ConcurrentRunner()
        tasks = [runner.make_task(f"t{i}", fn) for i in range(3)]
        report = runner.run_sync(tasks)
        assert report.succeeded == 3
        assert report.failed == 0

    def test_run_sync_results_correct(self):
        async def fn(): return "ok"

        runner = ConcurrentRunner()
        tasks = [runner.make_task("t", fn)]
        report = runner.run_sync(tasks)
        assert report.outcomes[0].result == "ok"

    def test_handles_exception_per_task(self):
        async def good(): return "good"
        async def bad(): raise ValueError("fail")

        runner = ConcurrentRunner()
        tasks = [runner.make_task("good", good), runner.make_task("bad", bad)]
        report = runner.run_sync(tasks)
        assert report.succeeded == 1
        assert report.failed == 1

    def test_error_message_captured(self):
        async def bad(): raise RuntimeError("something broke")

        runner = ConcurrentRunner()
        tasks = [runner.make_task("bad", bad)]
        report = runner.run_sync(tasks)
        assert "something broke" in report.outcomes[0].error

    def test_empty_task_list(self):
        runner = ConcurrentRunner()
        report = runner.run_sync([])
        assert report.outcomes == []
        assert report.total_elapsed == 0.0

    def test_make_task_generates_unique_ids(self):
        async def fn(): return 1

        ids = {ConcurrentRunner.make_task("t", fn).id for _ in range(20)}
        assert len(ids) == 20

    def test_make_task_sets_name(self):
        async def fn(): return 1

        spec = ConcurrentRunner.make_task("my_task", fn)
        assert spec.name == "my_task"

    def test_make_task_sets_timeout(self):
        async def fn(): return 1

        spec = ConcurrentRunner.make_task("t", fn, timeout=3.0)
        assert spec.timeout == 3.0

    def test_timeout_cancels_slow_task(self):
        async def slow():
            await asyncio.sleep(10)
            return "done"

        runner = ConcurrentRunner()
        tasks = [runner.make_task("slow", slow, timeout=0.05)]
        report = runner.run_sync(tasks)
        assert report.failed == 1
        assert report.outcomes[0].success is False

    def test_max_concurrency_respected(self):
        active = [0]
        max_active = [0]

        async def fn():
            active[0] += 1
            if active[0] > max_active[0]:
                max_active[0] = active[0]
            await asyncio.sleep(0.01)
            active[0] -= 1
            return active[0]

        runner = ConcurrentRunner(max_concurrency=2)
        tasks = [runner.make_task(f"t{i}", fn) for i in range(6)]
        runner.run_sync(tasks)
        assert max_active[0] <= 2

    def test_elapsed_measured(self):
        async def fn():
            await asyncio.sleep(0.01)
            return 1

        runner = ConcurrentRunner()
        tasks = [runner.make_task("t", fn)]
        report = runner.run_sync(tasks)
        assert report.outcomes[0].elapsed >= 0.0
        assert report.total_elapsed >= 0.0

    def test_all_tasks_run(self):
        results = []

        async def fn():
            results.append(1)
            return 1

        runner = ConcurrentRunner()
        tasks = [runner.make_task(f"t{i}", fn) for i in range(5)]
        runner.run_sync(tasks)
        assert len(results) == 5
