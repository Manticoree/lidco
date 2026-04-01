"""Loop progress tracking and stuck detection (task 1055)."""

from __future__ import annotations

from dataclasses import dataclass

from lidco.autonomous.loop_config import IterationResult


class LoopProgressTracker:
    """Immutable-style progress tracker for autonomous loop iterations.

    Each ``record()`` call returns a **new** tracker instance with the
    iteration appended, leaving the original unchanged.
    """

    def __init__(self, iterations: tuple[IterationResult, ...] = ()) -> None:
        self._iterations = iterations

    # -- public properties ------------------------------------------------

    @property
    def iterations(self) -> tuple[IterationResult, ...]:
        return self._iterations

    # -- recording --------------------------------------------------------

    def record(self, iteration: IterationResult) -> "LoopProgressTracker":
        """Return a new tracker with *iteration* appended."""
        return LoopProgressTracker(self._iterations + (iteration,))

    # -- analysis ---------------------------------------------------------

    def is_stuck(self, window: int = 3) -> bool:
        """Return True if the last *window* outputs are identical."""
        if len(self._iterations) < window:
            return False
        recent = [it.output.strip() for it in self._iterations[-window:]]
        first = recent[0]
        if not first:
            return False
        return all(r == first for r in recent)

    def progress_rate(self) -> float:
        """Estimate completion progress as a float in [0, 1].

        Heuristic: ratio of claimed-complete iterations to total, capped at
        the last iteration's claim.  Falls back to iteration count over 10
        when no claims are present.
        """
        if not self._iterations:
            return 0.0

        # If the last iteration claimed complete, treat as 1.0
        if self._iterations[-1].claimed_complete:
            return 1.0

        # Simple linear heuristic based on iteration count (assumes ~10 max)
        return min(1.0, len(self._iterations) / 10.0)

    def estimated_remaining(self) -> int:
        """Estimate iterations remaining (0 means done or unable to estimate)."""
        rate = self.progress_rate()
        if rate >= 1.0:
            return 0
        if rate <= 0.0:
            return 10
        total_estimated = len(self._iterations) / rate
        remaining = total_estimated - len(self._iterations)
        return max(0, int(remaining))

    def summary(self) -> str:
        """Return a human-readable progress summary."""
        n = len(self._iterations)
        if n == 0:
            return "No iterations recorded."

        claimed = sum(1 for it in self._iterations if it.claimed_complete)
        total_ms = sum(it.duration_ms for it in self._iterations)
        avg_ms = total_ms // n if n else 0
        stuck = self.is_stuck()
        rate = self.progress_rate()

        parts = [
            f"Iterations: {n}",
            f"Claimed complete: {claimed}",
            f"Avg duration: {avg_ms}ms",
            f"Progress: {rate:.0%}",
        ]
        if stuck:
            parts.append("WARNING: loop appears stuck")
        remaining = self.estimated_remaining()
        parts.append(f"Est. remaining: {remaining}")

        return " | ".join(parts)


__all__ = [
    "LoopProgressTracker",
]
