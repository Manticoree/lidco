"""TranscriptSearchIndex — keyword search over conversation turns.

Task 735: Q120.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchMatch:
    turn_index: int
    snippet: str
    score: int


@dataclass
class SearchResultSet:
    query: str
    matches: list[SearchMatch] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.matches)


class TranscriptSearchIndex:
    """In-memory full-text search over conversation turns."""

    def __init__(self, turns: list[dict]) -> None:
        self._turns = list(turns)

    def update(self, turns: list[dict]) -> None:
        self._turns = list(turns)

    def search(self, query: str) -> SearchResultSet:
        """Search turns for *query* words (case-insensitive)."""
        query = query.strip()
        if not query:
            return SearchResultSet(query=query)

        # Extract alphabetic words from query
        words = re.findall(r"[a-zA-Z0-9]+", query.lower())
        if not words:
            return SearchResultSet(query=query)

        matches: list[SearchMatch] = []

        for idx, turn in enumerate(self._turns):
            content = turn.get("content", "") or ""
            role = turn.get("role", "") or ""
            text = f"{role} {content}".lower()

            score = sum(1 for w in words if w in text)
            if score == 0:
                continue

            snippet = content[:100]
            matches.append(SearchMatch(turn_index=idx, snippet=snippet, score=score))

        # Sort by score descending
        matches.sort(key=lambda m: m.score, reverse=True)
        return SearchResultSet(query=query, matches=matches)


class Navigator:
    """Navigate through a SearchResultSet one match at a time."""

    def __init__(self, result_set: Optional[SearchResultSet] = None) -> None:
        self._result_set: Optional[SearchResultSet] = result_set
        self._index: int = 0

    def load(self, result_set: SearchResultSet) -> None:
        self._result_set = result_set
        self._index = 0

    def has_results(self) -> bool:
        return self._result_set is not None and self._result_set.count > 0

    def current(self) -> Optional[SearchMatch]:
        if not self.has_results():
            return None
        return self._result_set.matches[self._index]  # type: ignore[union-attr]

    def next(self) -> Optional[SearchMatch]:
        if not self.has_results():
            return None
        matches = self._result_set.matches  # type: ignore[union-attr]
        if self._index < len(matches) - 1:
            self._index += 1
        return matches[self._index]

    def prev(self) -> Optional[SearchMatch]:
        if not self.has_results():
            return None
        matches = self._result_set.matches  # type: ignore[union-attr]
        if self._index > 0:
            self._index -= 1
        return matches[self._index]

    def position(self) -> tuple[int, int]:
        """Return (current_index, total)."""
        if not self.has_results():
            return (0, 0)
        return (self._index, self._result_set.count)  # type: ignore[union-attr]
