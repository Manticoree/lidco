"""Semantic memory (v2) — stores facts about codebase, architecture, conventions.

Named SemanticMemory2 to avoid conflict with the existing
``lidco.memory.semantic_memory`` module.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import List


@dataclass
class Fact:
    """A single fact entry."""

    id: str
    content: str
    category: str
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower()))


class SemanticMemory2:
    """Store and query facts about a codebase."""

    def __init__(self) -> None:
        self._facts: dict[str, Fact] = {}

    def add_fact(self, fact: dict) -> Fact:
        """Add a fact from a dict.

        Required keys: content.
        Optional keys: category, confidence, tags.
        """
        if not fact.get("content"):
            raise ValueError("content is required")

        f = Fact(
            id=uuid.uuid4().hex[:12],
            content=fact["content"],
            category=fact.get("category", "general"),
            confidence=float(fact.get("confidence", 1.0)),
            timestamp=fact.get("timestamp", time.time()),
            tags=list(fact.get("tags", [])),
        )
        self._facts[f.id] = f
        return f

    def query(self, query: str) -> list[Fact]:
        """Search facts by keyword overlap with content+category+tags."""
        if not query.strip():
            return []
        tokens = _tokenize(query)
        scored: list[tuple[float, Fact]] = []
        for f in self._facts.values():
            fact_tokens = _tokenize(f.content) | _tokenize(f.category)
            for tag in f.tags:
                fact_tokens |= _tokenize(tag)
            overlap = len(tokens & fact_tokens)
            if overlap > 0:
                scored.append((overlap * f.confidence, f))
        scored.sort(key=lambda x: -x[0])
        return [f for _, f in scored]

    def decay(self, days: int) -> int:
        """Remove facts older than *days* days.  Returns count of removed facts."""
        cutoff = time.time() - days * 86400
        to_remove = [fid for fid, f in self._facts.items() if f.timestamp < cutoff]
        for fid in to_remove:
            del self._facts[fid]
        return len(to_remove)

    def facts(self) -> list[Fact]:
        """Return all facts."""
        return list(self._facts.values())
