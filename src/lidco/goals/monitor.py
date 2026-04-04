"""ProgressMonitor — track goal completion progress."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubtaskStatus:
    """Status of a single subtask."""

    subtask_id: str
    status: str = "pending"  # pending | in_progress | done | blocked


class ProgressMonitor:
    """Track progress of subtasks toward goal completion."""

    def __init__(self) -> None:
        self._statuses: dict[str, SubtaskStatus] = {}
        self._blockers: list[str] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def add_subtask(self, subtask_id: str) -> None:
        """Register a subtask for tracking."""
        if subtask_id not in self._statuses:
            self._statuses[subtask_id] = SubtaskStatus(subtask_id=subtask_id)

    def update(self, subtask_id: str, status: str) -> None:
        """Update the status of a subtask.

        Raises :class:`KeyError` if the subtask has not been added.
        Valid statuses: pending, in_progress, done, blocked.
        """
        valid = {"pending", "in_progress", "done", "blocked"}
        if status not in valid:
            raise ValueError(f"Invalid status {status!r}; must be one of {valid}")
        if subtask_id not in self._statuses:
            raise KeyError(f"Unknown subtask: {subtask_id}")
        self._statuses[subtask_id] = SubtaskStatus(
            subtask_id=subtask_id, status=status,
        )

    def completion_pct(self) -> float:
        """Return completion percentage (0.0–100.0)."""
        if not self._statuses:
            return 0.0
        done = sum(1 for s in self._statuses.values() if s.status == "done")
        return (done / len(self._statuses)) * 100.0

    def blockers(self) -> list[str]:
        """Return the list of blocker descriptions."""
        return list(self._blockers)

    def add_blocker(self, description: str) -> None:
        """Record a blocker."""
        self._blockers.append(description)

    def remove_blocker(self, description: str) -> None:
        """Remove a blocker by description."""
        if description in self._blockers:
            self._blockers.remove(description)

    def report(self) -> dict:
        """Generate a progress report dict."""
        return {
            "total": len(self._statuses),
            "done": sum(1 for s in self._statuses.values() if s.status == "done"),
            "in_progress": sum(
                1 for s in self._statuses.values() if s.status == "in_progress"
            ),
            "blocked": sum(
                1 for s in self._statuses.values() if s.status == "blocked"
            ),
            "pending": sum(
                1 for s in self._statuses.values() if s.status == "pending"
            ),
            "completion_pct": self.completion_pct(),
            "blockers": self.blockers(),
        }
