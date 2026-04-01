"""Tests for lidco.tasks.store — TaskStore persistent storage."""
from __future__ import annotations

import os
import pytest

from lidco.tasks.store import StoredTask, TaskStatus, TaskStore, TaskStoreError


class TestTaskStore:
    def test_create_returns_stored_task(self):
        store = TaskStore()
        task = store.create("build", description="Build the project")
        assert isinstance(task, StoredTask)
        assert task.name == "build"
        assert task.description == "Build the project"
        assert task.status == TaskStatus.PENDING
        assert len(task.id) == 8

    def test_get_existing_task(self):
        store = TaskStore()
        created = store.create("test")
        fetched = store.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "test"

    def test_get_nonexistent_returns_none(self):
        store = TaskStore()
        assert store.get("nonexist") is None

    def test_update_status(self):
        store = TaskStore()
        task = store.create("run")
        updated = store.update_status(task.id, TaskStatus.RUNNING)
        assert updated.status == TaskStatus.RUNNING

    def test_update_status_with_output_and_error(self):
        store = TaskStore()
        task = store.create("run")
        updated = store.update_status(task.id, TaskStatus.DONE, output="ok", error="")
        assert updated.output == "ok"
        assert updated.status == TaskStatus.DONE

    def test_update_status_not_found_raises(self):
        store = TaskStore()
        with pytest.raises(TaskStoreError):
            store.update_status("bad_id", TaskStatus.DONE)

    def test_list_tasks_all(self):
        store = TaskStore()
        store.create("a")
        store.create("b")
        tasks = store.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_filter_by_status(self):
        store = TaskStore()
        store.create("a")
        t2 = store.create("b")
        store.update_status(t2.id, TaskStatus.DONE)
        pending = store.list_tasks(status=TaskStatus.PENDING)
        done = store.list_tasks(status=TaskStatus.DONE)
        assert len(pending) == 1
        assert len(done) == 1

    def test_delete(self):
        store = TaskStore()
        task = store.create("x")
        assert store.delete(task.id) is True
        assert store.get(task.id) is None

    def test_delete_nonexistent(self):
        store = TaskStore()
        assert store.delete("nope") is False

    def test_count(self):
        store = TaskStore()
        store.create("a")
        store.create("b")
        assert store.count() == 2
        assert store.count(status=TaskStatus.PENDING) == 2
        assert store.count(status=TaskStatus.DONE) == 0

    def test_clear(self):
        store = TaskStore()
        store.create("a")
        store.create("b")
        removed = store.clear()
        assert removed == 2
        assert store.count() == 0

    def test_persistence_with_file(self, tmp_path):
        db_path = tmp_path / "tasks.db"
        store1 = TaskStore(db_path)
        store1.create("persist")
        # Re-open
        store2 = TaskStore(db_path)
        tasks = store2.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].name == "persist"

    def test_create_with_metadata(self):
        store = TaskStore()
        task = store.create("m", metadata={"key": "val"})
        fetched = store.get(task.id)
        assert fetched is not None
        assert fetched.metadata == {"key": "val"}
