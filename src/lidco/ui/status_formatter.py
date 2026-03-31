"""Coloured status line formatter with spinner and unit helpers (Q139/829)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StatusEntry:
    """Recorded status message."""

    label: str
    status: str
    detail: Optional[str]
    timestamp: float


class StatusFormatter:
    """Produce consistently formatted status strings."""

    SPINNER_FRAMES = "\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"

    def __init__(self) -> None:
        self._history: list[StatusEntry] = []

    # -- status helpers ----------------------------------------------------

    def _record(self, label: str, status: str, detail: Optional[str]) -> None:
        self._history.append(
            StatusEntry(label=label, status=status, detail=detail, timestamp=time.time())
        )

    def success(self, label: str, detail: Optional[str] = None) -> str:
        """Format a success line: ``v Label -- detail``."""
        self._record(label, "success", detail)
        suffix = f" -- {detail}" if detail else ""
        return f"v {label}{suffix}"

    def error(self, label: str, detail: Optional[str] = None) -> str:
        """Format an error line: ``x Label -- detail``."""
        self._record(label, "error", detail)
        suffix = f" -- {detail}" if detail else ""
        return f"x {label}{suffix}"

    def warning(self, label: str, detail: Optional[str] = None) -> str:
        """Format a warning line: ``! Label -- detail``."""
        self._record(label, "warning", detail)
        suffix = f" -- {detail}" if detail else ""
        return f"! {label}{suffix}"

    def info(self, label: str, detail: Optional[str] = None) -> str:
        """Format an info line: ``> Label -- detail``."""
        self._record(label, "info", detail)
        suffix = f" -- {detail}" if detail else ""
        return f"> {label}{suffix}"

    def spinner_frame(self, label: str, frame_idx: int) -> str:
        """Return a spinner animation frame for *label*."""
        char = self.SPINNER_FRAMES[frame_idx % len(self.SPINNER_FRAMES)]
        return f"{char} {label}"

    # -- formatting helpers ------------------------------------------------

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Human-readable duration string."""
        if seconds < 0:
            seconds = 0.0
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        if minutes < 60:
            return f"{minutes}m {secs}s"
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"

    @staticmethod
    def format_bytes(n: int) -> str:
        """Human-readable byte size."""
        if n < 0:
            n = 0
        if n < 1024:
            return f"{n} B"
        if n < 1024 * 1024:
            return f"{n / 1024:.1f} KB"
        if n < 1024 * 1024 * 1024:
            return f"{n / (1024 * 1024):.1f} MB"
        return f"{n / (1024 * 1024 * 1024):.1f} GB"

    # -- history -----------------------------------------------------------

    @property
    def history(self) -> list[StatusEntry]:
        """Return all recorded status entries."""
        return list(self._history)
