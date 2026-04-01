"""Auto-gather relevant context files."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextEntry:
    """A single context source entry."""

    path: str
    relevance: float
    tokens_estimate: int = 0
    reason: str = ""


@dataclass(frozen=True)
class AssemblyResult:
    """Result of context assembly."""

    entries: tuple[ContextEntry, ...] = ()
    total_tokens: int = 0
    budget_used: float = 0.0


class ContextAssembler:
    """Select most relevant context files within a token budget."""

    def __init__(self, token_budget: int = 100000) -> None:
        self._budget = token_budget
        self._sources: dict[str, dict[str, Any]] = {}

    def add_source(
        self,
        path: str,
        content: str,
        relevance: float = 0.5,
    ) -> None:
        """Register a source file with its content and relevance."""
        self._sources[path] = {
            "content": content,
            "relevance": relevance,
            "tokens": self.estimate_tokens(content),
        }

    def assemble(
        self,
        query: str,
        max_files: int = 20,
    ) -> AssemblyResult:
        """Select the most relevant sources within the token budget."""
        if not self._sources:
            return AssemblyResult()

        # Boost relevance if query keywords appear in the content
        query_words = set(query.lower().split())
        scored: list[tuple[float, str]] = []
        for path, info in self._sources.items():
            content_lower = info["content"].lower()
            bonus = sum(
                0.1 for w in query_words if w in content_lower
            )
            final_relevance = min(info["relevance"] + bonus, 1.0)
            scored.append((final_relevance, path))

        scored.sort(key=lambda t: t[0], reverse=True)

        entries: list[ContextEntry] = []
        total_tokens = 0
        for relevance, path in scored[:max_files]:
            info = self._sources[path]
            tokens = info["tokens"]
            if total_tokens + tokens > self._budget:
                continue
            total_tokens += tokens
            entries.append(
                ContextEntry(
                    path=path,
                    relevance=round(relevance, 4),
                    tokens_estimate=tokens,
                    reason="relevance match",
                )
            )

        budget_used = total_tokens / self._budget if self._budget > 0 else 0.0
        return AssemblyResult(
            entries=tuple(entries),
            total_tokens=total_tokens,
            budget_used=round(budget_used, 4),
        )

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: len(text) / 4."""
        return max(len(text) // 4, 1)

    def set_budget(self, tokens: int) -> None:
        """Update the token budget."""
        self._budget = tokens

    def clear(self) -> None:
        """Remove all sources."""
        self._sources.clear()

    def source_count(self) -> int:
        """Return number of registered sources."""
        return len(self._sources)
