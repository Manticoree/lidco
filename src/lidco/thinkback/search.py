"""Search across thinking blocks."""
from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass(frozen=True)
class SearchResult:
    """A single search hit within a thinking block."""

    turn: int
    line: int
    text: str
    score: float = 1.0
    context: str = ""


class ThinkingSearch:
    """Search content across thinking blocks."""

    def __init__(self) -> None:
        self._total_searches: int = 0

    def search(
        self,
        blocks: list[dict],
        query: str,
        regex: bool = False,
    ) -> list[SearchResult]:
        """Search all blocks for *query*, return matches with line numbers."""
        self._total_searches += 1
        results: list[SearchResult] = []
        pattern = re.compile(query) if regex else None
        for blk in blocks:
            turn = blk.get("turn", 0)
            content = blk.get("content", "")
            lines = content.splitlines()
            for idx, line in enumerate(lines, start=1):
                matched = False
                score = 0.0
                if pattern is not None:
                    if pattern.search(line):
                        matched = True
                        score = 1.0
                else:
                    lower_line = line.lower()
                    lower_query = query.lower()
                    if lower_query in lower_line:
                        matched = True
                        score = 1.0 if lower_query == lower_line.strip() else 0.8
                if matched:
                    ctx = self._build_context(lines, idx - 1)
                    results.append(
                        SearchResult(
                            turn=turn,
                            line=idx,
                            text=line.strip(),
                            score=score,
                            context=ctx,
                        )
                    )
        return results

    def search_turn_range(
        self,
        blocks: list[dict],
        query: str,
        start_turn: int = 0,
        end_turn: int = 999999,
    ) -> list[SearchResult]:
        """Search only blocks within [start_turn, end_turn]."""
        filtered = [
            b for b in blocks if start_turn <= b.get("turn", 0) <= end_turn
        ]
        return self.search(filtered, query)

    def rank_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Sort results by score descending."""
        return sorted(results, key=lambda r: r.score, reverse=True)

    def count_matches(self, blocks: list[dict], query: str) -> int:
        """Count total matches across all blocks."""
        return len(self.search(blocks, query))

    def summary(self, results: list[SearchResult]) -> str:
        """Human-readable summary of search results."""
        if not results:
            return "No matches found."
        turns = {r.turn for r in results}
        return (
            f"{len(results)} matches across {len(turns)} turns"
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(lines: list[str], idx: int, radius: int = 1) -> str:
        start = max(0, idx - radius)
        end = min(len(lines), idx + radius + 1)
        return "\n".join(lines[start:end])
