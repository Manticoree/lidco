"""Adaptive context paging — Task 307.

Dynamically ranks context chunks (files, RAG snippets, history summaries)
by relevance to the current query, then fills the token budget from highest
to lowest priority.  Acts as an "OS for context" — a scheduler that decides
what fits in the finite context window.

Usage::

    pager = ContextPager(token_budget=16_000)
    pager.add(ContextChunk(content="...", source="src/auth.py", priority=0.9))
    pager.add(ContextChunk(content="...", source="README.md", priority=0.3))
    result = pager.page()
    print(result.text)  # highest-priority content that fits in budget
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable


def _token_estimate(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


@dataclass
class ContextChunk:
    """A single piece of context with metadata."""

    content: str
    source: str = ""           # file path or label
    priority: float = 0.5      # 0.0–1.0; higher = more important
    chunk_type: str = "file"   # file | rag | history | rule | system

    @property
    def token_count(self) -> int:
        return _token_estimate(self.content)


@dataclass
class PageResult:
    """Result of a paging operation."""

    chunks: list[ContextChunk]
    total_tokens: int
    budget: int
    dropped_count: int
    dropped_sources: list[str]

    @property
    def text(self) -> str:
        """Concatenate all included chunks into a single context string."""
        parts: list[str] = []
        for chunk in self.chunks:
            if chunk.source:
                parts.append(f"### {chunk.source}\n{chunk.content}")
            else:
                parts.append(chunk.content)
        return "\n\n".join(parts)

    @property
    def utilization(self) -> float:
        """Fraction of budget used (0.0–1.0)."""
        if self.budget == 0:
            return 0.0
        return min(1.0, self.total_tokens / self.budget)


class ContextPager:
    """Ranks and packs context chunks within a token budget.

    Args:
        token_budget: Maximum tokens to include in the paged context.
        relevance_fn: Optional callable ``(chunk, query) -> float`` that
            augments base priority with query-specific relevance.
        type_weights: Multipliers per ``chunk_type`` (default: all 1.0).
    """

    _DEFAULT_TYPE_WEIGHTS: dict[str, float] = {
        "system": 1.0,
        "rule": 0.95,
        "history": 0.8,
        "file": 0.7,
        "rag": 0.65,
    }

    def __init__(
        self,
        token_budget: int = 8_000,
        relevance_fn: Callable[[ContextChunk, str], float] | None = None,
        type_weights: dict[str, float] | None = None,
    ) -> None:
        self._budget = token_budget
        self._relevance_fn = relevance_fn
        self._type_weights = dict(self._DEFAULT_TYPE_WEIGHTS)
        if type_weights:
            self._type_weights.update(type_weights)
        self._chunks: list[ContextChunk] = []

    def add(self, chunk: ContextChunk) -> None:
        """Add a context chunk."""
        self._chunks.append(chunk)

    def add_many(self, chunks: list[ContextChunk]) -> None:
        """Add multiple chunks at once."""
        self._chunks.extend(chunks)

    def clear(self) -> None:
        """Remove all pending chunks."""
        self._chunks.clear()

    def page(self, query: str = "") -> PageResult:
        """Pack the highest-priority chunks that fit within the token budget.

        Args:
            query: Current user message; used by ``relevance_fn`` if provided.

        Returns:
            PageResult with the selected chunks and metadata.
        """
        scored = self._score_all(query)
        # Sort descending by effective score
        scored.sort(key=lambda x: x[1], reverse=True)

        included: list[ContextChunk] = []
        dropped: list[ContextChunk] = []
        total_tokens = 0

        for chunk, _score in scored:
            tokens = chunk.token_count
            if total_tokens + tokens <= self._budget:
                included.append(chunk)
                total_tokens += tokens
            else:
                dropped.append(chunk)

        return PageResult(
            chunks=included,
            total_tokens=total_tokens,
            budget=self._budget,
            dropped_count=len(dropped),
            dropped_sources=[c.source for c in dropped if c.source],
        )

    def estimate_tokens(self) -> int:
        """Estimate total tokens if all chunks were included."""
        return sum(c.token_count for c in self._chunks)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def _score(self, chunk: ContextChunk, query: str) -> float:
        """Compute effective priority for a chunk."""
        base = chunk.priority * self._type_weights.get(chunk.chunk_type, 1.0)
        if self._relevance_fn and query:
            try:
                relevance = float(self._relevance_fn(chunk, query))
                # Blend base priority with query relevance (50/50)
                base = 0.5 * base + 0.5 * relevance
            except Exception:
                pass
        return max(0.0, min(1.0, base))

    def _score_all(self, query: str) -> list[tuple[ContextChunk, float]]:
        return [(c, self._score(c, query)) for c in self._chunks]
