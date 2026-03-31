"""DeadlineTracker — deadline management for tasks (stdlib only)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Deadline:
    """A tracked deadline."""

    task_id: str
    name: str
    due_at: float
    completed: bool = False
    completed_at: Optional[float] = None


class DeadlineTracker:
    """Track task deadlines, completions, and overdue status."""

    def __init__(self) -> None:
        self._deadlines: dict[str, Deadline] = {}

    def add(self, task_id: str, name: str, due_at: float) -> Deadline:
        """Register a deadline. Return the *Deadline*."""
        dl = Deadline(task_id=task_id, name=name, due_at=due_at)
        self._deadlines = {**self._deadlines, task_id: dl}
        return dl

    def complete(self, task_id: str) -> bool:
        """Mark *task_id* as completed. Return *True* if it existed."""
        dl = self._deadlines.get(task_id)
        if dl is None:
            return False
        # immutable-style update
        updated = Deadline(
            task_id=dl.task_id,
            name=dl.name,
            due_at=dl.due_at,
            completed=True,
            completed_at=time.time(),
        )
        self._deadlines = {**self._deadlines, task_id: updated}
        return True

    def overdue(self, now: float | None = None) -> list[Deadline]:
        """Return deadlines past due and not completed."""
        now = now if now is not None else time.time()
        return sorted(
            [d for d in self._deadlines.values() if not d.completed and d.due_at < now],
            key=lambda d: d.due_at,
        )

    def upcoming(self, seconds: float = 3600, now: float | None = None) -> list[Deadline]:
        """Return deadlines due within *seconds* from now, not completed."""
        now = now if now is not None else time.time()
        cutoff = now + seconds
        return sorted(
            [
                d
                for d in self._deadlines.values()
                if not d.completed and now <= d.due_at <= cutoff
            ],
            key=lambda d: d.due_at,
        )

    def summary(self, now: float | None = None) -> dict:
        """Return counts: total, completed, overdue, upcoming."""
        now = now if now is not None else time.time()
        all_dls = list(self._deadlines.values())
        completed = [d for d in all_dls if d.completed]
        overdue = [d for d in all_dls if not d.completed and d.due_at < now]
        upcoming = [d for d in all_dls if not d.completed and now <= d.due_at <= now + 3600]
        return {
            "total": len(all_dls),
            "completed": len(completed),
            "overdue": len(overdue),
            "upcoming": len(upcoming),
        }
