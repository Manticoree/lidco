"""Score context entries by relevance, recency, and reference count."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoredEntry:
    """An entry with computed priority score."""

    content: str
    score: float = 0.0
    recency: float = 0.0
    relevance: float = 0.0
    references: int = 0
    pinned: bool = False


class PriorityScorer:
    """Score and rank context entries for budget allocation."""

    def __init__(self, decay_rate: float = 0.1) -> None:
        self._decay_rate = decay_rate

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def score(
        self,
        content: str,
        timestamp: float = 0.0,
        references: int = 0,
        pinned: bool = False,
    ) -> ScoredEntry:
        """Compute a combined score for *content*."""
        if pinned:
            return ScoredEntry(
                content=content,
                score=1.0,
                recency=1.0,
                relevance=1.0,
                references=references,
                pinned=True,
            )

        now = time.time()
        elapsed = max(0.0, now - timestamp) if timestamp > 0 else 0.0
        recency = math.exp(-self._decay_rate * elapsed)

        # Simple relevance heuristic: longer content is more informative
        relevance = min(1.0, len(content) / 2000)

        ref_bonus = min(0.3, references * 0.05)
        combined = 0.4 * recency + 0.4 * relevance + 0.2 * ref_bonus

        return ScoredEntry(
            content=content,
            score=round(combined, 4),
            recency=round(recency, 4),
            relevance=round(relevance, 4),
            references=references,
            pinned=False,
        )

    def rank(self, entries: list[ScoredEntry]) -> list[ScoredEntry]:
        """Return entries sorted by score descending."""
        return sorted(entries, key=lambda e: e.score, reverse=True)

    def decay(self, entry: ScoredEntry, elapsed: float) -> ScoredEntry:
        """Return a new entry with decayed score."""
        if entry.pinned:
            return entry
        factor = math.exp(-self._decay_rate * elapsed)
        return ScoredEntry(
            content=entry.content,
            score=round(entry.score * factor, 4),
            recency=round(entry.recency * factor, 4),
            relevance=entry.relevance,
            references=entry.references,
            pinned=entry.pinned,
        )

    def filter_by_budget(
        self,
        entries: list[ScoredEntry],
        budget: int,
    ) -> list[ScoredEntry]:
        """Keep highest-scored entries until token *budget* is exhausted."""
        ranked = self.rank(entries)
        result: list[ScoredEntry] = []
        used = 0
        for entry in ranked:
            tokens = max(1, len(entry.content) // 4)
            if used + tokens > budget:
                break
            result.append(entry)
            used += tokens
        return result
