"""Evict lowest-importance messages to free token budget."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvictionResult:
    """Result of an eviction pass."""

    evicted_count: int
    tokens_freed: int = 0
    evicted_indices: tuple[int, ...] = ()
    remaining_count: int = 0


class SmartEvictor:
    """Remove low-importance messages to reclaim token budget."""

    def __init__(self, min_keep: int = 4) -> None:
        self._min_keep = min_keep

    def evict(
        self,
        messages: list[dict],
        scored: list[dict],
        target_tokens: int,
    ) -> tuple[list[dict], EvictionResult]:
        """Remove lowest-scored messages until *target_tokens* freed.

        Never evicts system messages or the last *min_keep* messages.
        """
        n = len(messages)
        protected = set(range(max(0, n - self._min_keep), n))
        # Also protect system messages
        for i, m in enumerate(messages):
            if m.get("role") == "system":
                protected.add(i)

        # Build eviction candidates sorted by importance ascending
        candidates = []
        for s in scored:
            idx = s.get("index", -1) if isinstance(s, dict) else getattr(s, "index", -1)
            imp = s.get("importance", 1.0) if isinstance(s, dict) else getattr(s, "importance", 1.0)
            if idx not in protected:
                candidates.append((idx, imp))
        candidates.sort(key=lambda x: x[1])

        freed = 0
        evicted: list[int] = []
        for idx, _imp in candidates:
            if freed >= target_tokens:
                break
            content = messages[idx].get("content", "") if idx < n else ""
            freed += self._estimate_tokens(content)
            evicted.append(idx)

        evicted_set = set(evicted)
        remaining = [m for i, m in enumerate(messages) if i not in evicted_set]
        return remaining, EvictionResult(
            evicted_count=len(evicted),
            tokens_freed=freed,
            evicted_indices=tuple(sorted(evicted)),
            remaining_count=len(remaining),
        )

    def evict_by_count(
        self,
        messages: list[dict],
        scored: list[dict],
        count: int,
    ) -> tuple[list[dict], EvictionResult]:
        """Remove exactly *count* lowest-importance messages."""
        n = len(messages)
        protected = set(range(max(0, n - self._min_keep), n))
        for i, m in enumerate(messages):
            if m.get("role") == "system":
                protected.add(i)

        candidates = []
        for s in scored:
            idx = s.get("index", -1) if isinstance(s, dict) else getattr(s, "index", -1)
            imp = s.get("importance", 1.0) if isinstance(s, dict) else getattr(s, "importance", 1.0)
            if idx not in protected:
                candidates.append((idx, imp))
        candidates.sort(key=lambda x: x[1])

        evicted = [idx for idx, _ in candidates[:count]]
        freed = sum(
            self._estimate_tokens(messages[i].get("content", ""))
            for i in evicted
            if i < n
        )
        evicted_set = set(evicted)
        remaining = [m for i, m in enumerate(messages) if i not in evicted_set]
        return remaining, EvictionResult(
            evicted_count=len(evicted),
            tokens_freed=freed,
            evicted_indices=tuple(sorted(evicted)),
            remaining_count=len(remaining),
        )

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(text) // 4

    def can_evict(self, messages: list[dict]) -> int:
        """Count of evictable messages (total - system - min_keep)."""
        n = len(messages)
        system_count = sum(1 for m in messages if m.get("role") == "system")
        non_evictable = system_count + self._min_keep
        return max(0, n - non_evictable)

    def summary(self, result: EvictionResult) -> str:
        """Human-readable eviction summary."""
        return (
            f"Evicted {result.evicted_count} messages, "
            f"freed ~{result.tokens_freed} tokens, "
            f"{result.remaining_count} remaining"
        )
