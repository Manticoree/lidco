"""Tests for CronRunner (T508)."""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from lidco.scheduler.cron_runner import CronRunner, CronTask, CronRunResult


class TestAddTask:
    def test_add_task_stores(self):
        runner = CronRunner()
        task = runner.add_task("test_task", "* * * * *", "do something")
        assert task.name == "test_task"
        assert task.cron_expr == "* * * * *"
        assert task.instruction == "do something"
        assert len(runner.list_tasks()) == 1

    def test_add_task_invalid_cron_raises(self):
        runner = CronRunner()
        with pytest.raises(ValueError):
            runner.add_task("bad", "* * *", "instruction")


class TestRemoveTask:
    def test_remove_task_returns_true(self):
        runner = CronRunner()
        runner.add_task("to_remove", "* * * * *", "work")
        result = runner.remove_task("to_remove")
        assert result is True
        assert len(runner.list_tasks()) == 0

    def test_remove_task_missing_returns_false(self):
        runner = CronRunner()
        result = runner.remove_task("nonexistent")
        assert result is False


class TestListTasks:
    def test_list_tasks_all(self):
        runner = CronRunner()
        runner.add_task("a", "* * * * *", "task a")
        runner.add_task("b", "0 * * * *", "task b")
        tasks = runner.list_tasks()
        assert len(tasks) == 2
        names = {t.name for t in tasks}
        assert names == {"a", "b"}


class TestParseCron:
    def test_parse_cron_wildcard_returns_none(self):
        result = CronRunner.parse_cron("* * * * *")
        assert result == {
            "minute": None,
            "hour": None,
            "day": None,
            "month": None,
            "weekday": None,
        }

    def test_parse_cron_specific_int(self):
        result = CronRunner.parse_cron("30 14 1 6 0")
        assert result["minute"] == 30
        assert result["hour"] == 14
        assert result["day"] == 1
        assert result["month"] == 6
        assert result["weekday"] == 0


class TestIsDue:
    def test_is_due_matches_time(self):
        import datetime
        runner = CronRunner()
        task = runner.add_task("check", "* * * * *", "run")
        # Wildcard matches anything; no last_run so it should be due
        assert runner.is_due(task) is True

    def test_is_due_wrong_hour_misses(self):
        import datetime
        runner = CronRunner()
        # Use specific hour that won't match current hour
        now_dt = datetime.datetime.now()
        wrong_hour = (now_dt.hour + 1) % 24
        task = runner.add_task("hourly", f"* {wrong_hour} * * *", "run hourly")
        now_ts = now_dt.timestamp()
        assert runner.is_due(task, now=now_ts) is False

    def test_is_due_respects_60s_cooldown(self):
        runner = CronRunner()
        task = runner.add_task("recent", "* * * * *", "run")
        now_ts = time.time()
        # Simulate last_run 30s ago
        task.last_run = now_ts - 30
        assert runner.is_due(task, now=now_ts) is False


class TestTick:
    def test_tick_runs_due_tasks(self):
        runner = CronRunner()
        runner.add_task("due_task", "* * * * *", "execute me")
        results = runner.tick(executor=lambda i: f"done: {i}")
        assert len(results) == 1
        assert results[0].task_name == "due_task"
        assert results[0].success is True
        assert "execute me" in results[0].output

    def test_tick_skips_disabled_tasks(self):
        runner = CronRunner()
        task = runner.add_task("disabled_task", "* * * * *", "skip me")
        task.enabled = False
        # Update the stored task
        runner._tasks = {task.name: task}
        results = runner.tick()
        assert results == []


class TestSaveLoadState:
    def test_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "scheduler.json"
            runner = CronRunner(state_path=state_path)
            runner.add_task("persisted", "0 12 * * *", "noon task")
            runner.save_state()

            runner2 = CronRunner(state_path=state_path)
            runner2.load_state()
            tasks = runner2.list_tasks()
            assert len(tasks) == 1
            assert tasks[0].name == "persisted"
            assert tasks[0].cron_expr == "0 12 * * *"
            assert tasks[0].instruction == "noon task"
