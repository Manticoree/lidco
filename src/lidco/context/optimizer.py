"""Context Optimizer — smart token-budget trimming for LLM prompts (stdlib only).

Manages a ranked list of context entries and trims them to fit within a
token budget while preserving the highest-priority content.  Useful for
keeping the most relevant file snippets, docs, and history in the prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContextSource(str, Enum):
    FILE = "file"
    HISTORY = "history"
    DOCS = "docs"
    SNIPPET = "snippet"
    SYSTEM = "system"


@dataclass
class ContextEntry:
    """A single piece of context that may be included in an LLM prompt."""

    content: str
    source: ContextSource = ContextSource.SNIPPET
    priority: float = 1.0          # higher = kept first
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Token estimation (cheap, no external deps)                           #
    # ------------------------------------------------------------------ #

    def token_count(self) -> int:
        """Estimate token count: ~4 chars per token (GPT-4 heuristic)."""
        return max(1, len(self.content) // 4)

    def word_count(self) -> int:
        return len(self.content.split())


@dataclass
class OptimizationResult:
    """Output of ContextOptimizer.optimize()."""

    included: list[ContextEntry]
    excluded: list[ContextEntry]
    total_tokens: int
    budget: int

    @property
    def utilization(self) -> float:
        return self.total_tokens / self.budget if self.budget else 0.0

    def prompt_text(self, separator: str = "\n\n") -> str:
        """Concatenate included entries into a single prompt string."""
        parts = []
        for entry in self.included:
            if entry.label:
                parts.append(f"[{entry.label}]\n{entry.content}")
            else:
                parts.append(entry.content)
        return separator.join(parts)


class ContextOptimizer:
    """Manages and optimises a pool of context entries for LLM prompts.

    Usage::

        opt = ContextOptimizer(token_budget=4096)
        opt.add(ContextEntry("def foo(): ...", source=ContextSource.FILE,
                             priority=2.0, label="main.py"))
        opt.add(ContextEntry("User asked about foo", source=ContextSource.HISTORY,
                             priority=1.0, label="history"))
        result = opt.optimize()
        prompt = result.prompt_text()

    Pinned entries (priority >= pin_threshold) are always included first;
    remaining slots are filled greedily by descending priority.
    """

    DEFAULT_BUDGET = 4096
    PIN_THRESHOLD = 10.0

    def __init__(
        self,
        token_budget: int = DEFAULT_BUDGET,
        pin_threshold: float = PIN_THRESHOLD,
    ) -> None:
        if token_budget < 1:
            raise ValueError("token_budget must be >= 1")
        self._budget = token_budget
        self._pin_threshold = pin_threshold
        self._entries: list[ContextEntry] = []

    # ------------------------------------------------------------------ #
    # Entry management                                                     #
    # ------------------------------------------------------------------ #

    def add(self, entry: ContextEntry) -> None:
        self._entries.append(entry)

    def add_text(
        self,
        content: str,
        *,
        source: ContextSource = ContextSource.SNIPPET,
        priority: float = 1.0,
        label: str = "",
    ) -> ContextEntry:
        entry = ContextEntry(content=content, source=source, priority=priority, label=label)
        self.add(entry)
        return entry

    def remove(self, label: str) -> int:
        """Remove all entries with the given label. Returns count removed."""
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.label != label]
        return before - len(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    @property
    def entries(self) -> list[ContextEntry]:
        return list(self._entries)

    @property
    def token_budget(self) -> int:
        return self._budget

    def total_tokens(self) -> int:
        return sum(e.token_count() for e in self._entries)

    # ------------------------------------------------------------------ #
    # Optimization                                                         #
    # ------------------------------------------------------------------ #

    def optimize(self) -> OptimizationResult:
        """Select entries that fit within the budget, highest priority first."""
        pinned = [e for e in self._entries if e.priority >= self._pin_threshold]
        normal = [e for e in self._entries if e.priority < self._pin_threshold]

        normal_sorted = sorted(normal, key=lambda e: e.priority, reverse=True)

        included: list[ContextEntry] = []
        excluded: list[ContextEntry] = []
        used_tokens = 0

        for entry in pinned:
            cost = entry.token_count()
            if used_tokens + cost <= self._budget:
                included.append(entry)
                used_tokens += cost
            else:
                excluded.append(entry)

        for entry in normal_sorted:
            cost = entry.token_count()
            if used_tokens + cost <= self._budget:
                included.append(entry)
                used_tokens += cost
            else:
                excluded.append(entry)

        return OptimizationResult(
            included=included,
            excluded=excluded,
            total_tokens=used_tokens,
            budget=self._budget,
        )

    # ------------------------------------------------------------------ #
    # Scoring helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def score_file_relevance(file_path: str, query: str) -> float:
        """Simple heuristic: how relevant is a file path to a query (0.0–1.0)."""
        if not query:
            return 0.5
        query_terms = set(re.split(r"[\s_\-./]+", query.lower()))
        path_terms = set(re.split(r"[\s_\-./]+", file_path.lower()))
        if not query_terms:
            return 0.5
        overlap = query_terms & path_terms
        return len(overlap) / len(query_terms)

    def set_budget(self, budget: int) -> None:
        if budget < 1:
            raise ValueError("budget must be >= 1")
        self._budget = budget

    def stats(self) -> dict[str, Any]:
        result = self.optimize()
        return {
            "entries": len(self._entries),
            "total_tokens": self.total_tokens(),
            "budget": self._budget,
            "included": len(result.included),
            "excluded": len(result.excluded),
            "utilization": round(result.utilization * 100, 1),
        }
