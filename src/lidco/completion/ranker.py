"""Completion ranking with multiple scoring factors."""
from __future__ import annotations

import difflib
import math
from dataclasses import dataclass, field


@dataclass
class RankedItem:
    """A ranked completion result."""

    text: str
    score: float
    factors: dict[str, float] = field(default_factory=dict)


class CompletionRanker:
    """Ranks completion candidates using multiple scoring factors."""

    def __init__(self) -> None:
        self._weights: dict[str, float] = {
            "prefix": 0.4,
            "similarity": 0.3,
            "frequency": 0.2,
            "recency": 0.1,
        }

    def rank(
        self,
        items: list[str],
        query: str,
        usage_counts: dict[str, int] | None = None,
        recency: dict[str, float] | None = None,
    ) -> list[RankedItem]:
        """Rank *items* against *query* returning scored results."""
        counts = usage_counts or {}
        rec = recency or {}

        results: list[RankedItem] = []
        for item in items:
            factors = {
                "prefix": self._prefix_score(item, query),
                "similarity": self._similarity_score(item, query),
                "frequency": self._frequency_score(item, counts),
                "recency": self._recency_score(item, rec),
            }
            total = sum(
                self._weights[k] * v for k, v in factors.items()
            )
            results.append(RankedItem(text=item, score=round(total, 6), factors=factors))

        results.sort(key=lambda r: (-r.score, r.text))
        return results

    def top(
        self,
        items: list[str],
        query: str,
        n: int = 5,
        **kwargs: object,
    ) -> list[RankedItem]:
        """Return the top *n* ranked items."""
        ranked = self.rank(
            items,
            query,
            usage_counts=kwargs.get("usage_counts"),  # type: ignore[arg-type]
            recency=kwargs.get("recency"),  # type: ignore[arg-type]
        )
        return ranked[:n]

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _prefix_score(item: str, query: str) -> float:
        """Exact prefix match bonus."""
        if not query:
            return 0.0
        lower_item = item.lower()
        lower_query = query.lower()
        if lower_item == lower_query:
            return 1.0
        if lower_item.startswith(lower_query):
            return 0.8
        return 0.0

    @staticmethod
    def _similarity_score(item: str, query: str) -> float:
        """String similarity via difflib."""
        if not query:
            return 0.0
        return difflib.SequenceMatcher(None, item.lower(), query.lower()).ratio()

    @staticmethod
    def _frequency_score(item: str, counts: dict[str, int]) -> float:
        """Usage frequency score (log-scaled, capped at 1.0)."""
        count = counts.get(item, 0)
        if count <= 0:
            return 0.0
        return min(1.0, math.log1p(count) / math.log1p(100))

    @staticmethod
    def _recency_score(item: str, recency: dict[str, float]) -> float:
        """Recent usage boost.  *recency* maps item -> timestamp (higher = more recent)."""
        ts = recency.get(item, 0.0)
        if ts <= 0:
            return 0.0
        # Normalize: assume recency values are 0-1 (pre-normalized) or raw timestamps.
        # If raw timestamps, we just use a sigmoid-like mapping.
        if ts <= 1.0:
            return ts
        # For large timestamps, apply a simple decay so more recent = higher score.
        return min(1.0, 1.0 / (1.0 + math.exp(-0.001 * (ts - 1_000_000_000))))
