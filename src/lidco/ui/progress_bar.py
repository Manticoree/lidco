"""Progress bar with ETA and percentage display (Q139/827)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProgressState:
    """Snapshot of progress bar state."""

    current: int
    total: int
    label: str
    started_at: float
    updated_at: float


class ProgressBar:
    """Renders a text-based progress bar with percentage, counts, and ETA.

    Example output::

        Indexing [████████████░░░░░░░░] 65% (13/20) 2.3s
    """

    def __init__(
        self,
        total: int,
        label: str = "",
        width: int = 40,
        fill_char: str = "\u2588",
        empty_char: str = "\u2591",
    ) -> None:
        if total < 0:
            raise ValueError("total must be non-negative")
        self._total = total
        self._label = label
        self._width = max(width, 1)
        self._fill_char = fill_char
        self._empty_char = empty_char
        self._current = 0
        self._started_at = time.monotonic()
        self._updated_at = self._started_at
        self._finished = False

    # -- mutators ----------------------------------------------------------

    def update(self, current: int) -> None:
        """Set current progress value."""
        self._current = max(0, min(current, self._total))
        self._updated_at = time.monotonic()

    def advance(self, n: int = 1) -> None:
        """Increment current progress by *n*."""
        self.update(self._current + n)

    def finish(self) -> None:
        """Mark the bar as 100% complete."""
        self._current = self._total
        self._updated_at = time.monotonic()
        self._finished = True

    # -- queries -----------------------------------------------------------

    @property
    def percentage(self) -> float:
        """Return completion percentage (0.0 – 100.0)."""
        if self._total == 0:
            return 100.0
        return (self._current / self._total) * 100.0

    @property
    def elapsed(self) -> float:
        """Seconds since the bar was created."""
        return self._updated_at - self._started_at

    @property
    def eta(self) -> Optional[float]:
        """Estimated seconds remaining, or ``None`` if unknown."""
        if self._current <= 0 or self._total == 0:
            return None
        elapsed = self.elapsed
        if elapsed <= 0:
            return None
        rate = self._current / elapsed
        remaining = self._total - self._current
        return remaining / rate

    @property
    def is_complete(self) -> bool:
        """Return ``True`` when progress has reached 100%."""
        return self._current >= self._total

    @property
    def state(self) -> ProgressState:
        """Return an immutable snapshot of current state."""
        return ProgressState(
            current=self._current,
            total=self._total,
            label=self._label,
            started_at=self._started_at,
            updated_at=self._updated_at,
        )

    # -- rendering ---------------------------------------------------------

    def render(self) -> str:
        """Return a single-line string representation of the bar.

        Format::

            Label [████░░░░] 65% (13/20) 2.3s
        """
        pct = self.percentage
        filled = int(self._width * pct / 100.0)
        bar = self._fill_char * filled + self._empty_char * (self._width - filled)
        elapsed_s = f"{self.elapsed:.1f}s"
        parts: list[str] = []
        if self._label:
            parts.append(self._label)
        parts.append(f"[{bar}]")
        parts.append(f"{pct:.0f}%")
        parts.append(f"({self._current}/{self._total})")
        parts.append(elapsed_s)
        return " ".join(parts)
