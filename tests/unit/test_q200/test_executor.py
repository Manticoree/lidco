"""Tests for lidco.tasks.executor — TaskExecutor."""
from __future__ import annotations

import time
import threading

from lidco.tasks.executor import ExecutionResult, TaskExecutor
from lidco.tasks.store import TaskStatus, TaskStore


class TestTaskExecutor:
    def test_execute_sync_success(self):
        store = TaskStore()
        task = store.create("add")
        executor = TaskExecutor(store=store)
        result = executor.execute_sync(task.id, lambda: 42)
        assert result.success is True
        assert result.output == "42"
        assert result.duration_ms > 0
        # Store should be updated
        updated = store.get(task.id)
        assert updated is not None
        assert updated.status == TaskStatus.DONE

    def test_execute_sync_failure(self):
        store = TaskStore()
        task = store.create("fail")
        executor = TaskExecutor(store=store)

        def _boom():
            raise ValueError("oops")

        result = executor.execute_sync(task.id, _boom)
        assert result.success is False
        assert "oops" in result.error
        updated = store.get(task.id)
        assert updated is not None
        assert updated.status == TaskStatus.FAILED

    def test_execute_sync_timeout(self):
        store = TaskStore()
        task = store.create("slow")
        executor = TaskExecutor(store=store)

        def _slow():
            time.sleep(5)
            return "done"

        result = executor.execute_sync(task.id, _slow, timeout=0.1)
        assert result.success is False
        assert result.error == "timeout"

    def test_execute_sync_no_store(self):
        executor = TaskExecutor()
        result = executor.execute_sync("t1", lambda: "hello")
        assert result.success is True
        assert result.output == "hello"

    def test_execute_sync_returns_none(self):
        executor = TaskExecutor()
        result = executor.execute_sync("t1", lambda: None)
        assert result.success is True
        assert result.output == ""

    def test_cancel(self):
        store = TaskStore()
        task = store.create("cancel-me")
        executor = TaskExecutor(store=store)

        def _slow():
            time.sleep(10)

        executor.submit(task.id, _slow)
        time.sleep(0.05)
        assert executor.cancel(task.id) is True

    def test_cancel_nonexistent(self):
        executor = TaskExecutor()
        assert executor.cancel("nope") is False

    def test_is_running(self):
        executor = TaskExecutor()

        event = threading.Event()

        def _wait():
            event.wait(timeout=5)

        executor.submit("r1", _wait)
        time.sleep(0.05)
        assert executor.is_running("r1") is True
        event.set()
        time.sleep(0.1)
        assert executor.is_running("r1") is False

    def test_active_count(self):
        executor = TaskExecutor()
        event = threading.Event()

        def _wait():
            event.wait(timeout=5)

        executor.submit("a1", _wait)
        executor.submit("a2", _wait)
        time.sleep(0.05)
        assert executor.active_count() >= 1
        event.set()
        time.sleep(0.2)
        assert executor.active_count() == 0
