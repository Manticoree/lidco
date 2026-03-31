"""NotificationQueue — priority notification queue with read tracking (stdlib only)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


_VALID_LEVELS = frozenset({"info", "warning", "error", "success"})


@dataclass
class Notification:
    """A single notification entry."""

    id: str
    level: str
    title: str
    message: str
    timestamp: float
    read: bool = False
    source: str = "system"


class NotificationQueue:
    """Bounded notification queue with read/unread tracking.

    Parameters
    ----------
    max_size:
        Maximum notifications retained.  Oldest are dropped when full.
    """

    def __init__(self, max_size: int = 100) -> None:
        self._max_size = max_size
        self._notifications: list[Notification] = []

    # ------------------------------------------------------------------ push

    def push(
        self,
        level: str,
        title: str,
        message: str,
        source: str = "system",
    ) -> Notification:
        """Create and enqueue a new notification."""
        if level not in _VALID_LEVELS:
            raise ValueError(f"Invalid level {level!r}; must be one of {sorted(_VALID_LEVELS)}")
        n = Notification(
            id=uuid.uuid4().hex[:12],
            level=level,
            title=title,
            message=message,
            timestamp=time.time(),
            source=source,
        )
        self._notifications.append(n)
        # Evict oldest when over capacity
        while len(self._notifications) > self._max_size:
            self._notifications.pop(0)
        return n

    # ------------------------------------------------------------------ pop / peek

    def pop(self) -> Optional[Notification]:
        """Return oldest unread notification and mark it read."""
        for n in self._notifications:
            if not n.read:
                n.read = True
                return n
        return None

    def peek(self) -> Optional[Notification]:
        """Return oldest unread notification without marking it read."""
        for n in self._notifications:
            if not n.read:
                return n
        return None

    # ------------------------------------------------------------------ mark read

    def mark_read(self, notification_id: str) -> bool:
        """Mark a specific notification as read.  Returns True if found."""
        for n in self._notifications:
            if n.id == notification_id:
                n.read = True
                return True
        return False

    def mark_all_read(self) -> None:
        """Mark every notification as read."""
        for n in self._notifications:
            n.read = True

    # ------------------------------------------------------------------ counts

    @property
    def unread_count(self) -> int:
        return sum(1 for n in self._notifications if not n.read)

    @property
    def total_count(self) -> int:
        return len(self._notifications)

    # ------------------------------------------------------------------ filter

    def by_level(self, level: str) -> list[Notification]:
        """Return all notifications matching *level*."""
        return [n for n in self._notifications if n.level == level]

    # ------------------------------------------------------------------ clear

    def clear_read(self) -> None:
        """Remove already-read notifications."""
        self._notifications = [n for n in self._notifications if not n.read]
