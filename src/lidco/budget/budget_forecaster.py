"""Forecast token budget depletion and recommend actions."""
from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(frozen=True)
class Forecast:
    """Immutable budget forecast snapshot."""

    current_used: int = 0
    total_budget: int = 128_000
    burn_rate: float = 0.0
    estimated_turns_remaining: int = 0
    estimated_depletion: float = 0.0
    recommendation: str = ""


class BudgetForecaster:
    """Track token usage over time and forecast depletion."""

    def __init__(self, total_budget: int = 128_000) -> None:
        self._total = total_budget
        self._samples: list[tuple[float, int]] = []

    # ------------------------------------------------------------------
    def record(self, used_tokens: int) -> None:
        """Append a usage sample with current timestamp."""
        self._samples = [*self._samples, (time.monotonic(), used_tokens)]

    # ------------------------------------------------------------------
    def burn_rate(self) -> float:
        """Tokens per second from up to the last 10 samples."""
        recent = self._samples[-10:] if len(self._samples) >= 2 else self._samples
        if len(recent) < 2:
            return 0.0
        dt = recent[-1][0] - recent[0][0]
        if dt <= 0:
            return 0.0
        d_tokens = recent[-1][1] - recent[0][1]
        return max(d_tokens / dt, 0.0)

    # ------------------------------------------------------------------
    def turns_remaining(self, tokens_per_turn: float = 0.0) -> int:
        """Estimate remaining turns before budget exhaustion."""
        if not self._samples:
            return 0
        current_used = self._samples[-1][1]
        remaining = self._total - current_used
        if remaining <= 0:
            return 0
        tpt = tokens_per_turn
        if tpt <= 0 and len(self._samples) >= 2:
            total_tokens = self._samples[-1][1] - self._samples[0][1]
            turns = len(self._samples) - 1
            tpt = total_tokens / turns if turns > 0 else 0
        if tpt <= 0:
            return 0
        return max(int(remaining / tpt), 0)

    # ------------------------------------------------------------------
    def forecast(self) -> Forecast:
        """Build a full *Forecast* with recommendation."""
        current_used = self._samples[-1][1] if self._samples else 0
        br = self.burn_rate()
        turns = self.turns_remaining()
        depletion = self.time_to_depletion()

        if turns <= 0:
            rec = "Over budget"
        elif turns < 5:
            rec = "Compact now"
        elif turns < 20:
            rec = "Compact soon"
        else:
            rec = "OK"

        return Forecast(
            current_used=current_used,
            total_budget=self._total,
            burn_rate=round(br, 2),
            estimated_turns_remaining=turns,
            estimated_depletion=round(depletion, 2),
            recommendation=rec,
        )

    # ------------------------------------------------------------------
    def time_to_depletion(self) -> float:
        """Seconds until budget exhausted at current burn rate."""
        if not self._samples:
            return 0.0
        remaining = self._total - self._samples[-1][1]
        br = self.burn_rate()
        if br <= 0 or remaining <= 0:
            return 0.0
        return remaining / br

    # ------------------------------------------------------------------
    def summary(self) -> str:
        fc = self.forecast()
        return (
            f"BudgetForecast: used={fc.current_used}/{fc.total_budget}, "
            f"burn={fc.burn_rate:.1f} tok/s, "
            f"turns_left={fc.estimated_turns_remaining}, "
            f"rec={fc.recommendation}"
        )
