"""Memory retrieval — combines episodic, procedural, and semantic sources.

Provides a unified interface to search across all memory types with
relevance scoring.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower()))


@runtime_checkable
class MemorySource(Protocol):
    """Protocol for any memory source that can participate in retrieval."""
    ...


@dataclass(frozen=True)
class RetrievalResult:
    """A single retrieval result with relevance score."""

    source: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


class MemoryRetrieval:
    """Unified retrieval across multiple memory sources."""

    def __init__(self) -> None:
        self._sources: dict[str, Any] = {}

    def add_source(self, name: str, memory: Any) -> None:
        """Register a memory source by name."""
        if not name:
            raise ValueError("name is required")
        self._sources[name] = memory

    def sources(self) -> list[str]:
        """Return registered source names."""
        return list(self._sources.keys())

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """Retrieve relevant items from all sources, ranked by relevance."""
        if not query.strip():
            return []

        results: list[RetrievalResult] = []
        query_tokens = _tokenize(query)

        for name, memory in self._sources.items():
            results.extend(self._query_source(name, memory, query, query_tokens))

        results.sort(key=lambda r: -r.score)
        return results[:top_k]

    def _query_source(
        self,
        name: str,
        memory: Any,
        query: str,
        query_tokens: set[str],
    ) -> list[RetrievalResult]:
        """Query a single source and return scored results."""
        results: list[RetrievalResult] = []

        # Episodic
        if hasattr(memory, "search") and hasattr(memory, "by_outcome"):
            for ep in memory.search(query):
                text = f"{ep.description} | {ep.strategy}"
                score = self._score(query_tokens, text)
                results.append(RetrievalResult(
                    source=name,
                    content=text,
                    score=score,
                    metadata={"type": "episode", "id": ep.id, "outcome": ep.outcome},
                ))

        # Procedural
        elif hasattr(memory, "find") and hasattr(memory, "generalize"):
            for proc in memory.find(query):
                text = f"{proc.name}: {', '.join(proc.steps)}"
                score = self._score(query_tokens, text) * (0.5 + 0.5 * proc.success_rate)
                results.append(RetrievalResult(
                    source=name,
                    content=text,
                    score=score,
                    metadata={"type": "procedure", "id": proc.id, "success_rate": proc.success_rate},
                ))

        # Semantic
        elif hasattr(memory, "query") and hasattr(memory, "facts"):
            for fact in memory.query(query):
                score = self._score(query_tokens, fact.content) * fact.confidence
                results.append(RetrievalResult(
                    source=name,
                    content=fact.content,
                    score=score,
                    metadata={"type": "fact", "id": fact.id, "category": fact.category},
                ))

        return results

    @staticmethod
    def _score(query_tokens: set[str], text: str) -> float:
        """Simple keyword overlap relevance score."""
        text_tokens = _tokenize(text)
        if not query_tokens or not text_tokens:
            return 0.0
        overlap = len(query_tokens & text_tokens)
        return overlap / max(len(query_tokens), 1)
