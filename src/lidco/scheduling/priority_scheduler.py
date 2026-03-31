"""PriorityScheduler — priority-based task scheduling (stdlib only)."""
from __future__ import annotations

import heapq
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ScheduledTask:
    """A task managed by the PriorityScheduler."""

    id: str
    name: str
    priority: int  # lower = higher priority
    category: str
    created_at: float
    payload: Any = None

    def __lt__(self, other: "ScheduledTask") -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


class PriorityScheduler:
    """Schedule tasks by priority; lower number = higher priority."""

    def __init__(self) -> None:
        self._heap: list[ScheduledTask] = []
        self._tasks: dict[str, ScheduledTask] = {}
        self._cancelled: set[str] = set()

    def schedule(
        self,
        name: str,
        priority: int = 0,
        category: str = "default",
        payload: Any = None,
    ) -> ScheduledTask:
        """Add a task to the scheduler and return it."""
        task = ScheduledTask(
            id=uuid.uuid4().hex,
            name=name,
            priority=priority,
            category=category,
            created_at=time.time(),
            payload=payload,
        )
        self._tasks = {**self._tasks, task.id: task}
        heapq.heappush(self._heap, task)
        return task

    def next(self) -> Optional[ScheduledTask]:
        """Pop and return the highest-priority task, or *None*."""
        while self._heap:
            task = heapq.heappop(self._heap)
            if task.id in self._cancelled:
                self._cancelled.discard(task.id)
                self._tasks.pop(task.id, None)
                continue
            self._tasks.pop(task.id, None)
            return task
        return None

    def peek(self) -> Optional[ScheduledTask]:
        """Return the highest-priority task without removing it, or *None*."""
        while self._heap:
            task = self._heap[0]
            if task.id in self._cancelled:
                heapq.heappop(self._heap)
                self._cancelled.discard(task.id)
                self._tasks.pop(task.id, None)
                continue
            return task
        return None

    def cancel(self, task_id: str) -> bool:
        """Cancel a scheduled task. Return *True* if it existed."""
        if task_id in self._tasks:
            self._cancelled.add(task_id)
            self._tasks.pop(task_id, None)
            return True
        return False

    def list_by_category(self, category: str) -> list[ScheduledTask]:
        """Return all non-cancelled tasks in *category*, ordered by priority."""
        return sorted(
            [t for t in self._tasks.values() if t.category == category],
            key=lambda t: (t.priority, t.created_at),
        )

    @property
    def size(self) -> int:
        """Number of non-cancelled tasks."""
        return len(self._tasks)

    @property
    def is_empty(self) -> bool:
        return self.size == 0
