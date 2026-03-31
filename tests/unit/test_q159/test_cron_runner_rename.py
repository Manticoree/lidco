"""Tests for Task 910 — CronTask / CronRunResult rename."""
from __future__ import annotations

import pytest

from lidco.scheduler.cron_runner import CronRunner, CronTask, CronRunResult


class TestCronTaskRename:
    """Task 910: ScheduledTask -> CronTask."""

    def test_cron_task_dataclass(self):
        task = CronTask(name="t", cron_expr="* * * * *", instruction="do it")
        assert task.name == "t"
        assert task.enabled is True
        assert task.run_count == 0

    def test_add_task_returns_cron_task(self):
        runner = CronRunner()
        task = runner.add_task("job", "* * * * *", "run me")
        assert isinstance(task, CronTask)

    def test_list_tasks_returns_cron_tasks(self):
        runner = CronRunner()
        runner.add_task("a", "* * * * *", "task a")
        tasks = runner.list_tasks()
        assert all(isinstance(t, CronTask) for t in tasks)


class TestCronRunResultRename:
    """Task 910: RunResult -> CronRunResult."""

    def test_cron_run_result_dataclass(self):
        r = CronRunResult(
            task_name="test",
            started_at=1.0,
            finished_at=2.0,
            success=True,
            output="done",
        )
        assert r.success
        assert r.task_name == "test"

    def test_tick_returns_cron_run_results(self):
        runner = CronRunner()
        runner.add_task("due", "* * * * *", "execute")
        results = runner.tick(executor=lambda i: f"ok: {i}")
        assert len(results) >= 1
        assert all(isinstance(r, CronRunResult) for r in results)


class TestBackwardCompatAliases:
    """Task 910: scheduler __init__ exports backward-compatible aliases."""

    def test_import_old_names_from_package(self):
        from lidco.scheduler import ScheduledTask, RunResult
        # They should be the same classes
        assert ScheduledTask is CronTask
        assert RunResult is CronRunResult

    def test_import_new_names_from_package(self):
        from lidco.scheduler import CronTask as CT, CronRunResult as CRR
        assert CT is CronTask
        assert CRR is CronRunResult
