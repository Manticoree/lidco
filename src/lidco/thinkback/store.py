"""Append-only store for model thinking/reasoning blocks."""
from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class ThinkingBlock:
    """Single thinking block captured from a model turn."""

    turn: int
    content: str
    timestamp: float = field(default_factory=time.time)
    token_count: int = 0
    model: str = ""


class ThinkingStore:
    """Append-only store for thinking blocks."""

    def __init__(self) -> None:
        self._blocks: list[ThinkingBlock] = []

    def append(self, turn: int, content: str, model: str = "") -> ThinkingBlock:
        """Append a new thinking block, auto-computing token_count."""
        token_count = len(content) // 4
        block = ThinkingBlock(
            turn=turn,
            content=content,
            token_count=token_count,
            model=model,
        )
        self._blocks = [*self._blocks, block]
        return block

    def get_by_turn(self, turn: int) -> list[ThinkingBlock]:
        """Return all blocks for a specific turn."""
        return [b for b in self._blocks if b.turn == turn]

    def get_all(self) -> list[ThinkingBlock]:
        """Return all stored blocks."""
        return list(self._blocks)

    def get_latest(self, count: int = 5) -> list[ThinkingBlock]:
        """Return the latest *count* blocks."""
        return list(self._blocks[-count:])

    def total_tokens(self) -> int:
        """Sum of token_count across all blocks."""
        return sum(b.token_count for b in self._blocks)

    def turn_count(self) -> int:
        """Number of unique turns."""
        return len({b.turn for b in self._blocks})

    def clear(self) -> None:
        """Remove all blocks."""
        self._blocks = []

    def summary(self) -> str:
        """Human-readable summary of store contents."""
        return (
            f"ThinkingStore: {len(self._blocks)} blocks, "
            f"{self.turn_count()} turns, "
            f"{self.total_tokens()} tokens"
        )
