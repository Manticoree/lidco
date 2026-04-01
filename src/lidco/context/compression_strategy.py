"""Pluggable compression strategies."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StrategyType(str, Enum):
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"


@dataclass(frozen=True)
class CompressionStats:
    """Statistics from a compression pass."""

    strategy: StrategyType
    original_tokens: int = 0
    compressed_tokens: int = 0
    ratio: float = 0.0
    turns_removed: int = 0


class CompressionStrategy:
    """Apply a named compression strategy to a message list."""

    def __init__(self, strategy: StrategyType = StrategyType.BALANCED) -> None:
        self._strategy = strategy

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    @property
    def strategy(self) -> StrategyType:
        return self._strategy

    def compress(
        self,
        messages: list[dict],
    ) -> tuple[list[dict], CompressionStats]:
        """Apply the configured strategy and return compressed list + stats."""
        original_tokens = self._estimate_tokens(messages)

        if self._strategy == StrategyType.AGGRESSIVE:
            compressed = self._aggressive(messages)
        elif self._strategy == StrategyType.CONSERVATIVE:
            compressed = self._conservative(messages)
        else:
            compressed = self._balanced(messages)

        compressed_tokens = self._estimate_tokens(compressed)
        ratio = compressed_tokens / original_tokens if original_tokens > 0 else 0.0
        turns_removed = len(messages) - len(compressed)

        stats = CompressionStats(
            strategy=self._strategy,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            ratio=round(ratio, 4),
            turns_removed=turns_removed,
        )
        return compressed, stats

    def get_target_ratio(self) -> float:
        """Target compression ratio for the strategy."""
        return {
            StrategyType.AGGRESSIVE: 0.3,
            StrategyType.BALANCED: 0.5,
            StrategyType.CONSERVATIVE: 0.7,
        }[self._strategy]

    def summary(self, stats: CompressionStats) -> str:
        """Human-readable summary of compression results."""
        return (
            f"Strategy: {stats.strategy.value} | "
            f"Original: {stats.original_tokens} tokens | "
            f"Compressed: {stats.compressed_tokens} tokens | "
            f"Ratio: {stats.ratio:.2%} | "
            f"Turns removed: {stats.turns_removed}"
        )

    # ------------------------------------------------------------------ #
    # Strategies                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _aggressive(messages: list[dict]) -> list[dict]:
        """Keep only system messages and last 5 non-system turns."""
        system = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        return system + non_system[-5:]

    @staticmethod
    def _balanced(messages: list[dict]) -> list[dict]:
        """Keep system + last 10 turns; summarize older non-system."""
        system = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        if len(non_system) <= 10:
            return system + non_system

        older = non_system[:-10]
        recent = non_system[-10:]

        # Summarize older turns into one message
        summary_lines: list[str] = []
        for m in older:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            first = content.split("\n", 1)[0][:120]
            summary_lines.append(f"[{role}] {first}")

        summary_msg = {"role": "assistant", "content": "\n".join(summary_lines)}
        return system + [summary_msg] + recent

    @staticmethod
    def _conservative(messages: list[dict]) -> list[dict]:
        """Keep system + last 20 turns; truncate long tool results in older."""
        system = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        if len(non_system) <= 20:
            return system + non_system

        older = non_system[:-20]
        recent = non_system[-20:]

        truncated: list[dict] = []
        for m in older:
            content = m.get("content", "")
            if m.get("role") == "tool" and len(content) > 200:
                truncated.append({**m, "content": content[:200] + "..."})
            else:
                truncated.append(dict(m))

        return system + truncated + recent

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _estimate_tokens(messages: list[dict]) -> int:
        total = 0
        for m in messages:
            total += max(1, len(m.get("content", "")) // 4)
        return total
