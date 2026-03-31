"""ToastManager — ephemeral toast-style messages (stdlib only)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

_LEVEL_LABELS = {
    "info": "INFO",
    "warning": "WARNING",
    "error": "ERROR",
    "success": "SUCCESS",
}


@dataclass
class Toast:
    """A single toast message."""

    message: str
    level: str
    duration: float = 3.0
    timestamp: float = field(default_factory=time.time)
    expired: bool = False


class ToastManager:
    """Manages ephemeral toast notifications with auto-expiry.

    Parameters
    ----------
    default_duration:
        Default display duration in seconds.
    """

    def __init__(self, default_duration: float = 3.0) -> None:
        self._default_duration = default_duration
        self._toasts: list[Toast] = []

    # ------------------------------------------------------------------ show

    def show(
        self,
        message: str,
        level: str = "info",
        duration: Optional[float] = None,
    ) -> Toast:
        """Create and display a new toast."""
        t = Toast(
            message=message,
            level=level,
            duration=duration if duration is not None else self._default_duration,
            timestamp=time.time(),
        )
        self._toasts.append(t)
        return t

    # ------------------------------------------------------------------ active / expire

    def active(self) -> list[Toast]:
        """Return non-expired toasts."""
        return [t for t in self._toasts if not t.expired]

    def expire_old(self) -> None:
        """Mark toasts as expired if their duration has elapsed."""
        now = time.time()
        for t in self._toasts:
            if not t.expired and (now - t.timestamp) >= t.duration:
                t.expired = True

    # ------------------------------------------------------------------ dismiss

    def dismiss(self, index: int) -> bool:
        """Manually expire toast at *index* in the active list.  Returns True on success."""
        active = self.active()
        if 0 <= index < len(active):
            active[index].expired = True
            return True
        return False

    def dismiss_all(self) -> None:
        """Expire all toasts."""
        for t in self._toasts:
            t.expired = True

    # ------------------------------------------------------------------ render

    def render(self, toast: Toast) -> str:
        """Render toast as ``[LEVEL] message (Ns)``."""
        label = _LEVEL_LABELS.get(toast.level, toast.level.upper())
        return f"[{label}] {toast.message} ({toast.duration:.0f}s)"

    # ------------------------------------------------------------------ history

    @property
    def history(self) -> list[Toast]:
        """Return all toasts (active + expired)."""
        return list(self._toasts)
