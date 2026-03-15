"""Tests for TaskQueue — Task 328."""

from __future__ import annotations

import time

import pytest

from lidco.cloud.task_queue import Task, TaskNotFoundError, TaskQueue, TaskState


@pytest.fixture
def queue(tmp_path):
    q = TaskQueue(db_path=tmp_path / "tasks.db")
    yield q
    q.close()


# ---------------------------------------------------------------------------
# Task dataclass
# ---------------------------------------------------------------------------

class TestTask:
    def test_is_terminal_done(self):
        t = Task(task_id="x", prompt="p", state="done")
        assert t.is_terminal is True

    def test_is_terminal_failed(self):
        assert Task(task_id="x", prompt="p", state="failed").is_terminal is True

    def test_is_terminal_cancelled(self):
        assert Task(task_id="x", prompt="p", state="cancelled").is_terminal is True

    def test_not_terminal_queued(self):
        assert Task(task_id="x", prompt="p", state="queued").is_terminal is False

    def test_duration_seconds(self):
        t = Task(task_id="x", prompt="p", started_at=100.0, finished_at=105.0)
        assert t.duration_seconds == 5.0

    def test_to_dict(self):
        t = Task(task_id="abc", prompt="do thing")
        d = t.to_dict()
        assert d["task_id"] == "abc"
        assert d["state"] == "queued"


# ---------------------------------------------------------------------------
# submit()
# ---------------------------------------------------------------------------

class TestTaskQueueSubmit:
    def test_submit_returns_id(self, queue):
        tid = queue.submit("Refactor auth")
        assert isinstance(tid, str)
        assert len(tid) > 0

    def test_submit_creates_task(self, queue):
        tid = queue.submit("Fix bug")
        task = queue.get(tid)
        assert task is not None
        assert task.state == TaskState.QUEUED
        assert task.prompt == "Fix bug"

    def test_submit_with_agent(self, queue):
        tid = queue.submit("Review code", agent="reviewer")
        task = queue.get(tid)
        assert task.agent == "reviewer"

    def test_submit_custom_id(self, queue):
        tid = queue.submit("task", task_id="my-custom-id")
        assert tid == "my-custom-id"

    def test_submit_increments_count(self, queue):
        assert queue.count() == 0
        queue.submit("task 1")
        queue.submit("task 2")
        assert queue.count() == 2


# ---------------------------------------------------------------------------
# start() / complete() / fail()
# ---------------------------------------------------------------------------

class TestTaskQueueLifecycle:
    def test_start_sets_running(self, queue):
        tid = queue.submit("task")
        queue.start(tid)
        task = queue.get(tid)
        assert task.state == TaskState.RUNNING
        assert task.started_at > 0

    def test_complete_sets_done(self, queue):
        tid = queue.submit("task")
        queue.complete(tid, result="all done")
        task = queue.get(tid)
        assert task.state == TaskState.DONE
        assert task.result == "all done"
        assert task.finished_at > 0

    def test_fail_sets_failed(self, queue):
        tid = queue.submit("task")
        queue.fail(tid, error="Something went wrong")
        task = queue.get(tid)
        assert task.state == TaskState.FAILED
        assert task.error == "Something went wrong"

    def test_start_missing_raises(self, queue):
        with pytest.raises(TaskNotFoundError):
            queue.start("nonexistent-id")

    def test_complete_missing_raises(self, queue):
        with pytest.raises(TaskNotFoundError):
            queue.complete("nonexistent-id")

    def test_fail_missing_raises(self, queue):
        with pytest.raises(TaskNotFoundError):
            queue.fail("nonexistent-id")


# ---------------------------------------------------------------------------
# cancel()
# ---------------------------------------------------------------------------

class TestTaskQueueCancel:
    def test_cancel_queued_task(self, queue):
        tid = queue.submit("task")
        assert queue.cancel(tid) is True
        assert queue.get(tid).state == TaskState.CANCELLED

    def test_cancel_running_task(self, queue):
        tid = queue.submit("task")
        queue.start(tid)
        assert queue.cancel(tid) is True

    def test_cancel_done_task_returns_false(self, queue):
        tid = queue.submit("task")
        queue.complete(tid)
        assert queue.cancel(tid) is False

    def test_cancel_missing_returns_false(self, queue):
        assert queue.cancel("ghost-id") is False


# ---------------------------------------------------------------------------
# list_tasks() / count()
# ---------------------------------------------------------------------------

class TestTaskQueueList:
    def test_list_all(self, queue):
        queue.submit("a")
        queue.submit("b")
        tasks = queue.list_tasks()
        assert len(tasks) == 2

    def test_list_by_state(self, queue):
        t1 = queue.submit("queued task")
        t2 = queue.submit("another task")
        queue.complete(t2, result="done")
        queued = queue.list_tasks(state=TaskState.QUEUED)
        assert len(queued) == 1
        assert queued[0].task_id == t1

    def test_count_by_state(self, queue):
        queue.submit("a")
        t2 = queue.submit("b")
        queue.complete(t2)
        assert queue.count(state=TaskState.QUEUED) == 1
        assert queue.count(state=TaskState.DONE) == 1

    def test_list_limit(self, queue):
        for _ in range(10):
            queue.submit("task")
        assert len(queue.list_tasks(limit=5)) == 5


# ---------------------------------------------------------------------------
# get() returns None for missing
# ---------------------------------------------------------------------------

class TestTaskQueueGet:
    def test_get_missing_returns_none(self, queue):
        assert queue.get("nonexistent") is None
