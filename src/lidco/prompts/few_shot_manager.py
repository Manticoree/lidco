"""Q246: Few-shot example manager — add, remove, select, and format examples."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Example:
    """A single few-shot example."""

    id: str
    input: str
    output: str
    tags: list[str] = field(default_factory=list)


class FewShotManager:
    """Manage few-shot examples with keyword-based selection."""

    def __init__(self) -> None:
        self._examples: list[Example] = []

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_example(
        self,
        input: str,
        output: str,
        tags: list[str] | None = None,
    ) -> str:
        """Add an example and return its id."""
        eid = uuid.uuid4().hex[:8]
        ex = Example(id=eid, input=input, output=output, tags=list(tags) if tags else [])
        self._examples = [*self._examples, ex]
        return eid

    def remove_example(self, example_id: str) -> bool:
        """Remove an example by id. Returns True if found."""
        before = len(self._examples)
        self._examples = [e for e in self._examples if e.id != example_id]
        return len(self._examples) < before

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select(
        self,
        query: str,
        limit: int = 3,
        token_budget: int | None = None,
    ) -> list[Example]:
        """Select examples by keyword relevance.

        Simple scoring: count query words found in input text + tags.
        If *token_budget* is set, stop adding examples once budget would be exceeded
        (rough estimate: 4 chars per token).
        """
        query_words = set(query.lower().split())
        if not query_words:
            selected = list(self._examples[:limit])
        else:
            def _score(ex: Example) -> int:
                haystack = set(ex.input.lower().split()) | {t.lower() for t in ex.tags}
                return len(query_words & haystack)

            ranked = sorted(self._examples, key=_score, reverse=True)
            selected = ranked[:limit]

        if token_budget is not None:
            chars_per_token = 4
            max_chars = token_budget * chars_per_token
            result: list[Example] = []
            used = 0
            for ex in selected:
                ex_chars = len(ex.input) + len(ex.output) + 20  # overhead
                if used + ex_chars > max_chars:
                    break
                result.append(ex)
                used += ex_chars
            return result

        return selected

    # ------------------------------------------------------------------
    # Listing / formatting
    # ------------------------------------------------------------------

    def list_examples(self) -> list[Example]:
        """Return all examples."""
        return list(self._examples)

    @staticmethod
    def format_examples(examples: list[Example]) -> str:
        """Format examples as ``Input: ...\\nOutput: ...`` blocks."""
        parts: list[str] = []
        for ex in examples:
            parts.append(f"Input: {ex.input}\nOutput: {ex.output}")
        return "\n\n".join(parts)
