"""Tests for T624 TaskScheduler."""
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from lidco.scheduler.task_scheduler import ScheduledTask, TaskRunResult, TaskScheduler


def _future_iso(seconds: int = 3600) -> str:
    return (datetime.now() + timedelta(seconds=seconds)).isoformat()


def _past_iso(seconds: int = 60) -> str:
    return (datetime.now() - timedelta(seconds=seconds)).isoformat()


class TestTaskScheduler:
    def _make(self, tmp_path):
        return TaskScheduler(store_path=tmp_path / "tasks.json")

    def test_add_interval_schedule(self, tmp_path):
        sched = self._make(tmp_path)
        task = sched.add("mytask", "echo hello", "every 10s")
        assert task.name == "mytask"
        assert task.command == "echo hello"
        assert task.schedule == "every 10s"
        assert task.enabled is True
        assert task.next_run > time.time()

    def test_add_iso_datetime_schedule(self, tmp_path):
        sched = self._make(tmp_path)
        future = _future_iso(3600)
        task = sched.add("iso_task", "echo iso", future)
        expected = datetime.fromisoformat(future).timestamp()
        assert abs(task.next_run - expected) < 1.0

    def test_add_invalid_schedule_raises(self, tmp_path):
        sched = self._make(tmp_path)
        with pytest.raises(ValueError, match="Unrecognised schedule"):
            sched.add("bad", "echo x", "bogus format")

    def test_remove_existing_returns_true(self, tmp_path):
        sched = self._make(tmp_path)
        task = sched.add("t", "echo x", "every 1h")
        assert sched.remove(task.id) is True

    def test_remove_nonexistent_returns_false(self, tmp_path):
        sched = self._make(tmp_path)
        assert sched.remove("nonexistent_id") is False

    def test_list_returns_all(self, tmp_path):
        sched = self._make(tmp_path)
        sched.add("a", "echo a", "every 1m")
        sched.add("b", "echo b", "every 2m")
        tasks = sched.list()
        assert len(tasks) == 2

    def test_get_existing(self, tmp_path):
        sched = self._make(tmp_path)
        task = sched.add("find_me", "echo x", "every 5s")
        found = sched.get(task.id)
        assert found is not None
        assert found.name == "find_me"

    def test_get_missing_returns_none(self, tmp_path):
        sched = self._make(tmp_path)
        assert sched.get("missing") is None

    def test_run_due_executes_due_task(self, tmp_path):
        sched = self._make(tmp_path)
        past = _past_iso(60)
        task = sched.add("due_task", "echo hello", past)
        # Patch subprocess to avoid real execution
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "hello"
        mock_proc.stderr = ""
        with patch("subprocess.run", return_value=mock_proc):
            results = sched.run_due()
        assert len(results) == 1
        assert results[0].task_name == "due_task"
        assert results[0].success is True

    def test_run_due_skips_future_task(self, tmp_path):
        sched = self._make(tmp_path)
        sched.add("future_task", "echo x", _future_iso(3600))
        results = sched.run_due()
        assert results == []

    def test_run_due_disables_oneshot(self, tmp_path):
        sched = self._make(tmp_path)
        past = _past_iso(60)
        task = sched.add("oneshot", "echo x", past)
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            sched.run_due()
        updated = sched.get(task.id)
        assert updated is not None
        assert updated.enabled is False

    def test_run_due_reschedules_recurring(self, tmp_path):
        sched = self._make(tmp_path)
        # Manually set next_run in the past for a recurring task
        task = sched.add("recurring", "echo x", "every 5m")
        # Modify next_run to be in the past by rewriting the JSON
        import json
        store = tmp_path / "tasks.json"
        data = json.loads(store.read_text())
        data[task.id]["next_run"] = time.time() - 10
        store.write_text(json.dumps(data))

        mock_proc = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            results = sched.run_due()
        assert len(results) == 1
        updated = sched.get(task.id)
        assert updated is not None
        assert updated.enabled is True
        assert updated.next_run > time.time()

    def test_run_due_increments_run_count(self, tmp_path):
        sched = self._make(tmp_path)
        past = _past_iso(60)
        task = sched.add("counter", "echo x", past)
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            sched.run_due()
        updated = sched.get(task.id)
        assert updated.run_count == 1

    def test_persistence_across_instances(self, tmp_path):
        path = tmp_path / "tasks.json"
        s1 = TaskScheduler(store_path=path)
        task = s1.add("persist", "echo p", "every 1h")
        s2 = TaskScheduler(store_path=path)
        assert s2.get(task.id) is not None

    def test_start_stop_thread(self, tmp_path):
        sched = self._make(tmp_path)
        sched.start(poll_interval=0.1)
        time.sleep(0.05)
        sched.stop()  # should not raise

    def test_task_run_result_format_summary(self, tmp_path):
        result = TaskRunResult(
            task_id="abc",
            task_name="my_task",
            command="echo hi",
            started_at=1000.0,
            finished_at=1001.5,
            returncode=0,
            stdout="hi",
            stderr="",
            success=True,
        )
        summary = result.format_summary()
        assert "my_task" in summary
        assert "OK" in summary
        assert "hi" in summary
