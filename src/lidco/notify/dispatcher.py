"""Cross-platform notification dispatcher."""
from __future__ import annotations

import sys
import time
import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Notification:
    """A single notification record."""

    id: str
    title: str
    message: str
    level: str = "info"
    timestamp: float = 0.0
    delivered: bool = False


class NotificationDispatcher:
    """Cross-platform notification dispatcher with history."""

    def __init__(self, enabled: bool = True, platform: str = "auto") -> None:
        self._enabled = enabled
        self._platform = platform if platform != "auto" else self._detect_platform()
        self._history: list[Notification] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, title: str, message: str, level: str = "info") -> Notification:
        """Create and optionally deliver a notification."""
        notification = Notification(
            id=uuid.uuid4().hex[:12],
            title=title,
            message=message,
            level=level,
            timestamp=time.time(),
            delivered=False,
        )
        delivered = self._deliver(notification)
        notification = Notification(
            id=notification.id,
            title=notification.title,
            message=notification.message,
            level=notification.level,
            timestamp=notification.timestamp,
            delivered=delivered,
        )
        self._history.append(notification)
        return notification

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    def history(self) -> list[Notification]:
        return list(self._history)

    def summary(self) -> dict:
        total = len(self._history)
        delivered = sum(1 for n in self._history if n.delivered)
        return {
            "total": total,
            "delivered": delivered,
            "enabled": self._enabled,
            "platform": self._platform,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _detect_platform(self) -> str:
        if sys.platform.startswith("win"):
            return "windows"
        if sys.platform == "darwin":
            return "macos"
        if sys.platform.startswith("linux"):
            return "linux"
        return "unknown"

    def _deliver(self, notification: Notification) -> bool:
        """Platform-specific delivery stub. Returns *True* if enabled."""
        return self._enabled
