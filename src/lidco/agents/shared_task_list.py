"""SharedTaskList — thread-safe task pool for multi-agent self-assignment."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskStatus(Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    DONE = "done"
    FAILED = "failed"


@dataclass
class SharedTask:
    id: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None
    result: Optional[str] = None
    created_at: str = ""


class SharedTaskList:
    """Thread-safe task pool for multi-agent self-assignment."""

    def __init__(self) -> None:
        self._tasks: list[SharedTask] = []
        self._lock = threading.Lock()

    def add(self, title: str) -> SharedTask:
        """Add a new PENDING task and return it."""
        task = SharedTask(
            id=uuid.uuid4().hex[:12],
            title=title,
            status=TaskStatus.PENDING,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        with self._lock:
            self._tasks.append(task)
        return task

    def claim(self, agent_name: str) -> Optional[SharedTask]:
        """Atomically claim one PENDING task. Returns None if none available."""
        with self._lock:
            for task in self._tasks:
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.CLAIMED
                    task.assigned_to = agent_name
                    return task
        return None

    def complete(self, task_id: str, result: str) -> None:
        """Mark a task as DONE with a result string."""
        with self._lock:
            for task in self._tasks:
                if task.id == task_id:
                    task.status = TaskStatus.DONE
                    task.result = result
                    return
            raise KeyError(f"Task '{task_id}' not found")

    def fail(self, task_id: str, error: str) -> None:
        """Mark a task as FAILED with an error string."""
        with self._lock:
            for task in self._tasks:
                if task.id == task_id:
                    task.status = TaskStatus.FAILED
                    task.result = error
                    return
            raise KeyError(f"Task '{task_id}' not found")

    def list_pending(self) -> list[SharedTask]:
        """Return all PENDING tasks."""
        with self._lock:
            return [t for t in self._tasks if t.status == TaskStatus.PENDING]

    def list_all(self) -> list[SharedTask]:
        """Return all tasks."""
        with self._lock:
            return list(self._tasks)

    def pending_count(self) -> int:
        """Count of PENDING tasks."""
        with self._lock:
            return sum(1 for t in self._tasks if t.status == TaskStatus.PENDING)

    def done_count(self) -> int:
        """Count of DONE tasks."""
        with self._lock:
            return sum(1 for t in self._tasks if t.status == TaskStatus.DONE)

    def reset(self) -> None:
        """Clear all tasks."""
        with self._lock:
            self._tasks.clear()
