"""ProgressDashboard widget — multi-task progress, nested tasks, ETA."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from lidco.widgets.framework import Widget


@dataclass
class TaskProgress:
    """Tracks progress of a single task."""

    id: str
    name: str
    progress: float = 0.0
    status: str = "pending"
    parent_id: str | None = None
    started_at: float | None = None
    eta_seconds: float | None = None


class ProgressDashboard(Widget):
    """Dashboard showing multi-task progress with nesting and ETA."""

    def __init__(self) -> None:
        super().__init__(id="progress-dashboard", title="Progress Dashboard")
        self._tasks: dict[str, TaskProgress] = {}

    def add_task(self, name: str, parent_id: str | None = None) -> TaskProgress:
        task_id = uuid.uuid4().hex[:8]
        task = TaskProgress(
            id=task_id,
            name=name,
            parent_id=parent_id,
            started_at=time.time(),
        )
        self._tasks[task_id] = task
        return task

    def update_task(
        self, task_id: str, progress: float, status: str | None = None
    ) -> TaskProgress | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.progress = min(max(progress, 0.0), 100.0)
        if status is not None:
            task.status = status
        elif task.progress >= 100.0:
            task.status = "complete"
        else:
            task.status = "running"
        # Estimate ETA
        if task.started_at is not None and task.progress > 0:
            elapsed = time.time() - task.started_at
            remaining = (100.0 - task.progress) / task.progress * elapsed
            task.eta_seconds = round(remaining, 1)
        return task

    def complete_task(self, task_id: str) -> TaskProgress | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.progress = 100.0
        task.status = "complete"
        task.eta_seconds = 0.0
        return task

    def remove_task(self, task_id: str) -> bool:
        if task_id not in self._tasks:
            return False
        del self._tasks[task_id]
        # Also remove children
        child_ids = [t.id for t in self._tasks.values() if t.parent_id == task_id]
        for cid in child_ids:
            del self._tasks[cid]
        return True

    def get_task(self, task_id: str) -> TaskProgress | None:
        return self._tasks.get(task_id)

    def children(self, parent_id: str) -> list[TaskProgress]:
        return [t for t in self._tasks.values() if t.parent_id == parent_id]

    def all_tasks(self) -> list[TaskProgress]:
        return list(self._tasks.values())

    def overall_progress(self) -> float:
        """Average progress of top-level tasks only."""
        top_level = [t for t in self._tasks.values() if t.parent_id is None]
        if not top_level:
            return 0.0
        return sum(t.progress for t in top_level) / len(top_level)

    def render(self) -> str:
        lines: list[str] = [f"[ProgressDashboard] {len(self._tasks)} tasks, overall={self.overall_progress():.1f}%"]
        for task in self._tasks.values():
            indent = "  " if task.parent_id else ""
            eta = f" ETA={task.eta_seconds:.0f}s" if task.eta_seconds else ""
            lines.append(f"{indent}{task.name}: {task.progress:.0f}% [{task.status}]{eta}")
        return "\n".join(lines)

    def summary(self) -> dict:
        return {
            "total": len(self._tasks),
            "complete": sum(1 for t in self._tasks.values() if t.status == "complete"),
            "running": sum(1 for t in self._tasks.values() if t.status == "running"),
            "pending": sum(1 for t in self._tasks.values() if t.status == "pending"),
            "overall_progress": round(self.overall_progress(), 1),
        }
