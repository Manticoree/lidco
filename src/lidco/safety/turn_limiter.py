"""Conversation turn limits for safety."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LimitAction(str, Enum):
    """Action to take based on turn count."""

    CONTINUE = "continue"
    WARN = "warn"
    STOP = "stop"
    OVERRIDE = "override"


@dataclass(frozen=True)
class TurnLimitResult:
    """Result of a turn limit check."""

    current_turn: int
    max_turns: int
    action: LimitAction
    message: str = ""


class TurnLimiter:
    """Configurable conversation turn limiter."""

    def __init__(self, max_turns: int = 100, warn_at: float = 0.8) -> None:
        self._max_turns = max_turns
        self._warn_at = warn_at

    def check(self, current_turn: int) -> TurnLimitResult:
        """Check turn count and return the appropriate action."""
        if current_turn >= self._max_turns:
            return TurnLimitResult(
                current_turn=current_turn,
                max_turns=self._max_turns,
                action=LimitAction.STOP,
                message=f"Turn limit reached ({current_turn}/{self._max_turns}).",
            )
        warn_threshold = int(self._warn_at * self._max_turns)
        if current_turn >= warn_threshold:
            remaining = self._max_turns - current_turn
            return TurnLimitResult(
                current_turn=current_turn,
                max_turns=self._max_turns,
                action=LimitAction.WARN,
                message=f"Approaching turn limit: {remaining} turn(s) remaining.",
            )
        return TurnLimitResult(
            current_turn=current_turn,
            max_turns=self._max_turns,
            action=LimitAction.CONTINUE,
        )

    def override(self, additional: int = 20) -> None:
        """Extend the max turns by the given amount."""
        self._max_turns = self._max_turns + additional

    def remaining(self, current_turn: int) -> int:
        """Return how many turns remain."""
        return max(0, self._max_turns - current_turn)

    def percentage(self, current_turn: int) -> float:
        """Return the percentage of turns used."""
        if self._max_turns <= 0:
            return 1.0
        return current_turn / self._max_turns

    def set_limit(self, max_turns: int) -> None:
        """Set a new max turn limit."""
        self._max_turns = max_turns

    def summary(self, current_turn: int) -> str:
        """One-line summary of current turn status."""
        pct = self.percentage(current_turn)
        return (
            f"Turn {current_turn}/{self._max_turns} "
            f"({pct:.0%} used, {self.remaining(current_turn)} remaining)"
        )
