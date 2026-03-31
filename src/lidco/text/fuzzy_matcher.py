"""Q137 — FuzzyMatcher: fuzzy string matching via difflib."""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Optional


@dataclass
class MatchResult:
    """Result of a fuzzy match."""

    candidate: str
    score: float
    index: int


class FuzzyMatcher:
    """Fuzzy string matching against a list of candidates."""

    def __init__(self, candidates: list[str]) -> None:
        self._candidates = list(candidates)

    @property
    def candidates(self) -> list[str]:
        return list(self._candidates)

    def _score(self, query: str, candidate: str) -> float:
        return difflib.SequenceMatcher(None, query, candidate).ratio()

    def match(self, query: str, threshold: float = 0.6) -> list[MatchResult]:
        """Return candidates with score >= threshold, sorted by score desc."""
        results: list[MatchResult] = []
        for idx, cand in enumerate(self._candidates):
            score = self._score(query, cand)
            if score >= threshold:
                results.append(MatchResult(candidate=cand, score=score, index=idx))
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def best_match(self, query: str) -> Optional[MatchResult]:
        """Return the best matching candidate, or None if no candidates."""
        if not self._candidates:
            return None
        best: Optional[MatchResult] = None
        for idx, cand in enumerate(self._candidates):
            score = self._score(query, cand)
            if best is None or score > best.score:
                best = MatchResult(candidate=cand, score=score, index=idx)
        return best

    def match_all(self, query: str) -> list[MatchResult]:
        """Return all candidates with their scores, sorted by score desc."""
        results = [
            MatchResult(candidate=cand, score=self._score(query, cand), index=idx)
            for idx, cand in enumerate(self._candidates)
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results
