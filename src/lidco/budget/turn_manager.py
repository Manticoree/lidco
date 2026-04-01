"""Per-turn budget lifecycle management."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TurnBudget:
    """Immutable record for a single turn's token usage."""

    turn: int = 0
    pre_tokens: int = 0
    post_tokens: int = 0
    delta: int = 0
    compacted: bool = False
    timestamp: float = field(default_factory=time.time)


class TurnBudgetManager:
    """Track token consumption on a per-turn basis."""

    def __init__(self, total_budget: int = 128000) -> None:
        self._turns: list[TurnBudget] = []
        self._current_turn: int = 0
        self._total: int = total_budget
        self._pending_pre: int = 0

    def begin_turn(self, current_tokens: int) -> int:
        """Start a new turn, recording *current_tokens* as pre-state."""
        self._current_turn += 1
        self._pending_pre = current_tokens
        return self._current_turn

    def end_turn(self, current_tokens: int, compacted: bool = False) -> TurnBudget:
        """Finish the current turn, recording *current_tokens* as post-state."""
        delta = current_tokens - self._pending_pre
        turn = TurnBudget(
            turn=self._current_turn,
            pre_tokens=self._pending_pre,
            post_tokens=current_tokens,
            delta=delta,
            compacted=compacted,
        )
        self._turns = [*self._turns, turn]
        return turn

    def get_turn(self, turn: int) -> TurnBudget | None:
        """Return the :class:`TurnBudget` for *turn*, or ``None``."""
        for t in self._turns:
            if t.turn == turn:
                return t
        return None

    def get_recent(self, count: int = 5) -> list[TurnBudget]:
        """Return the last *count* turns."""
        return list(self._turns[-count:])

    def average_delta(self) -> float:
        """Average tokens added per turn."""
        if not self._turns:
            return 0.0
        return sum(t.delta for t in self._turns) / len(self._turns)

    def should_warn(self) -> bool:
        """True if projected usage in 5 turns exceeds remaining budget."""
        if not self._turns:
            return False
        last_post = self._turns[-1].post_tokens
        remaining = self._total - last_post
        return self.average_delta() * 5 > remaining

    def remaining(self, current_tokens: int) -> int:
        """Tokens remaining given *current_tokens*."""
        return max(0, self._total - current_tokens)

    def summary(self) -> str:
        """Human-readable summary of turn history."""
        lines = [
            f"Total budget: {self._total:,}",
            f"Turns recorded: {len(self._turns)}",
            f"Avg delta: {self.average_delta():,.0f}",
        ]
        if self._turns:
            last = self._turns[-1]
            lines.append(f"Last post_tokens: {last.post_tokens:,}")
            lines.append(f"Remaining: {self.remaining(last.post_tokens):,}")
        return "\n".join(lines)
