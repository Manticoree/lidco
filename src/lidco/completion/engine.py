"""Intelligent code completion engine."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompletionItem:
    """A single completion suggestion."""

    text: str
    kind: str
    score: float = 0.0
    detail: str = ""


class CompletionEngine:
    """Prefix-based code completion with scoring and context awareness."""

    def __init__(self) -> None:
        self._symbols: list[dict[str, str]] = []
        self._context: dict[str, object] = {}
        self._query_count: int = 0

    # ------------------------------------------------------------------
    # Symbol management
    # ------------------------------------------------------------------

    def add_symbol(self, name: str, kind: str, detail: str = "") -> None:
        """Register a symbol for completion."""
        self._symbols = [*self._symbols, {"name": name, "kind": kind, "detail": detail}]

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def complete(self, prefix: str, limit: int = 10) -> list[CompletionItem]:
        """Return completions matching *prefix*, sorted by score descending."""
        self._query_count += 1
        if not prefix:
            return []

        lower = prefix.lower()
        matches: list[CompletionItem] = []
        for sym in self._symbols:
            name_lower = sym["name"].lower()
            if name_lower.startswith(lower):
                score = self._score(sym, prefix)
                matches.append(
                    CompletionItem(
                        text=sym["name"],
                        kind=sym["kind"],
                        score=score,
                        detail=sym["detail"],
                    )
                )

        matches = sorted(matches, key=lambda c: (-c.score, c.text))
        return matches[:limit]

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def add_context(self, context: dict[str, object]) -> None:
        """Store context used for boosting scores."""
        self._context = {**self._context, **context}

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, object]:
        """Return engine statistics."""
        return {
            "symbols": len(self._symbols),
            "queries": self._query_count,
            "context_keys": len(self._context),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _score(self, sym: dict[str, str], prefix: str) -> float:
        """Compute a relevance score for *sym* given *prefix*."""
        base = 1.0
        # Exact case match bonus
        if sym["name"].startswith(prefix):
            base += 1.0
        # Shorter names rank higher (less noise)
        length_penalty = len(sym["name"]) / 100.0
        base -= length_penalty
        # Context boost
        if self._context.get("current_file"):
            base += 0.1
        if sym["kind"] == self._context.get("preferred_kind"):
            base += 0.5
        return round(base, 4)
