"""Backpressure controller for streaming flow control.

Monitors buffer usage and signals when producers should pause or resume,
using configurable high/low watermarks.
"""
from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field


class BackpressureState(enum.Enum):
    """Current state of the backpressure controller."""

    FLOWING = "flowing"
    PAUSED = "paused"


@dataclass(frozen=True)
class BackpressureSignal:
    """Signal returned by backpressure check."""

    action: str  # "pause", "resume", "ok"
    buffer_usage: float


class BackpressureController:
    """Monitors buffer fill level and signals pause/resume to producers.

    Parameters
    ----------
    token_rate_limit:
        Maximum tokens per second (advisory).
    high_watermark:
        Fraction (0-1) at which to signal *pause*.
    low_watermark:
        Fraction (0-1) at which to signal *resume* after a pause.
    buffer_size:
        Logical buffer capacity used for watermark calculations.
    """

    def __init__(
        self,
        *,
        token_rate_limit: int = 1000,
        high_watermark: float = 0.8,
        low_watermark: float = 0.2,
        buffer_size: int = 10000,
    ) -> None:
        if not 0.0 <= low_watermark < high_watermark <= 1.0:
            raise ValueError(
                "Watermarks must satisfy 0 <= low_watermark < high_watermark <= 1"
            )
        if buffer_size <= 0:
            raise ValueError("buffer_size must be positive")
        if token_rate_limit <= 0:
            raise ValueError("token_rate_limit must be positive")

        self._token_rate_limit = token_rate_limit
        self._high_watermark = high_watermark
        self._low_watermark = low_watermark
        self._buffer_size = buffer_size
        self._state = BackpressureState.FLOWING
        self._created_at = time.monotonic()
        self._pause_count = 0
        self._resume_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, current_buffer_usage: int) -> BackpressureSignal:
        """Evaluate buffer usage and return an appropriate signal.

        Parameters
        ----------
        current_buffer_usage:
            Number of items currently in the buffer.

        Returns
        -------
        BackpressureSignal
            action is ``"pause"`` when usage crosses the high watermark,
            ``"resume"`` when it drops below the low watermark while paused,
            or ``"ok"`` otherwise.
        """
        usage_fraction = current_buffer_usage / self._buffer_size if self._buffer_size else 0.0
        usage_fraction = min(usage_fraction, 1.0)

        if self._state is BackpressureState.FLOWING:
            if usage_fraction >= self._high_watermark:
                self._state = BackpressureState.PAUSED
                self._pause_count += 1
                return BackpressureSignal(action="pause", buffer_usage=usage_fraction)
            return BackpressureSignal(action="ok", buffer_usage=usage_fraction)

        # Currently PAUSED
        if usage_fraction <= self._low_watermark:
            self._state = BackpressureState.FLOWING
            self._resume_count += 1
            return BackpressureSignal(action="resume", buffer_usage=usage_fraction)
        return BackpressureSignal(action="ok", buffer_usage=usage_fraction)

    def pause(self) -> None:
        """Manually pause the controller."""
        if self._state is not BackpressureState.PAUSED:
            self._state = BackpressureState.PAUSED
            self._pause_count += 1

    def resume(self) -> None:
        """Manually resume the controller."""
        if self._state is not BackpressureState.FLOWING:
            self._state = BackpressureState.FLOWING
            self._resume_count += 1

    @property
    def is_paused(self) -> bool:
        """Return ``True`` when the controller is in the PAUSED state."""
        return self._state is BackpressureState.PAUSED

    def stats(self) -> dict:
        """Return current controller statistics."""
        return {
            "rate": self._token_rate_limit,
            "state": self._state.value,
            "high_watermark": self._high_watermark,
            "low_watermark": self._low_watermark,
            "buffer_size": self._buffer_size,
            "pause_count": self._pause_count,
            "resume_count": self._resume_count,
            "uptime": time.monotonic() - self._created_at,
        }
