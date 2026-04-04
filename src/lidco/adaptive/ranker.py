"""ContextRanker — rank context items by relevance using word-overlap heuristic."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ContextItem:
    """A piece of context with text and metadata."""

    text: str
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    weight: float = 1.0


class ContextRanker:
    """Rank context items by relevance to a query."""

    def __init__(self, recency_weight: float = 0.3, similarity_weight: float = 0.7) -> None:
        self._items: list[ContextItem] = []
        self.recency_weight = recency_weight
        self.similarity_weight = similarity_weight

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_item(self, item: ContextItem) -> None:
        """Add a context item."""
        self._items.append(item)

    def items(self) -> list[ContextItem]:
        """Return all stored items."""
        return list(self._items)

    def clear(self) -> None:
        """Remove all items."""
        self._items.clear()

    def score_item(self, item: ContextItem, query: str) -> float:
        """Score a single *item* against *query* (0.0–1.0)."""
        sim = self._similarity(item.text, query)
        rec = self._recency(item)
        return (self.similarity_weight * sim + self.recency_weight * rec) * item.weight

    def rank(self, items: list[ContextItem], query: str) -> list[ContextItem]:
        """Return *items* sorted by relevance to *query* (best first)."""
        scored = [(self.score_item(it, query), it) for it in items]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [it for _, it in scored]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {w.lower().strip(".,;:!?()[]{}\"'") for w in text.split() if w.strip()}

    def _similarity(self, text: str, query: str) -> float:
        """Word-overlap Jaccard similarity."""
        tokens_a = self._tokenize(text)
        tokens_b = self._tokenize(query)
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union) if union else 0.0

    def _recency(self, item: ContextItem) -> float:
        """Score from 0.0 (old) to 1.0 (recent).

        Items within the last 60 seconds score ~1.0; items older than 1 hour score ~0.0.
        """
        age = time.time() - item.timestamp
        if age <= 0:
            return 1.0
        # Exponential decay: half-life ~300s (5 min)
        return max(0.0, min(1.0, 2.0 ** (-age / 300.0)))
