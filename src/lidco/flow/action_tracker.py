"""Action Tracker — records user actions for flow analysis."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class TrackedAction:
    """A single tracked user action."""

    action_type: str  # edit, command, search, error, read
    detail: str
    timestamp: float
    file_path: str | None = None
    success: bool = True


class ActionTracker:
    """Tracks user actions with bounded history."""

    def __init__(self, max_history: int = 500) -> None:
        self._max_history = max_history
        self._actions: deque[TrackedAction] = deque(maxlen=max_history)

    def track(
        self,
        action_type: str,
        detail: str,
        file_path: str | None = None,
        success: bool = True,
    ) -> None:
        """Record an action."""
        action = TrackedAction(
            action_type=action_type,
            detail=detail,
            timestamp=time.time(),
            file_path=file_path,
            success=success,
        )
        self._actions.append(action)

    def recent(self, limit: int = 20) -> list[TrackedAction]:
        """Return the most recent *limit* actions (newest last)."""
        items = list(self._actions)
        return items[-limit:] if len(items) > limit else list(items)

    def by_type(self, action_type: str) -> list[TrackedAction]:
        """Return all actions matching *action_type*."""
        return [a for a in self._actions if a.action_type == action_type]

    def by_file(self, file_path: str) -> list[TrackedAction]:
        """Return all actions targeting *file_path*."""
        return [a for a in self._actions if a.file_path == file_path]

    def error_rate(self, window: int = 50) -> float:
        """Ratio of failed actions in the last *window* actions."""
        items = list(self._actions)
        tail = items[-window:] if len(items) > window else items
        if not tail:
            return 0.0
        errors = sum(1 for a in tail if not a.success)
        return errors / len(tail)

    def most_active_files(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return (file_path, count) pairs sorted descending by count."""
        counts: dict[str, int] = {}
        for a in self._actions:
            if a.file_path is not None:
                counts[a.file_path] = counts.get(a.file_path, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return ranked[:limit]

    def clear(self) -> None:
        """Remove all tracked actions."""
        self._actions.clear()

    def stats(self) -> dict:
        """Return totals by action type."""
        result: dict[str, int] = {}
        for a in self._actions:
            result[a.action_type] = result.get(a.action_type, 0) + 1
        return result
