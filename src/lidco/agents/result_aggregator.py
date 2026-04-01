"""Merge multiple agent results."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentResult:
    """Result from a single agent."""

    agent_name: str
    content: str
    confidence: float = 0.5
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class AggregatedResult:
    """Combined result from multiple agents."""

    results: tuple[AgentResult, ...] = ()
    merged_content: str = ""
    consensus: float = 0.0


class ResultAggregator:
    """Collect and merge agent results."""

    def __init__(self) -> None:
        self._results: tuple[AgentResult, ...] = ()

    def add_result(
        self,
        agent_name: str,
        content: str,
        confidence: float = 0.5,
    ) -> AgentResult:
        """Add a result and return it."""
        result = AgentResult(
            agent_name=agent_name,
            content=content,
            confidence=confidence,
        )
        self._results = (*self._results, result)
        return result

    def merge(self) -> AggregatedResult:
        """Merge all results: join content with headers, average confidence."""
        if not self._results:
            return AggregatedResult()
        sections: list[str] = []
        total_conf = 0.0
        for r in self._results:
            sections = [*sections, f"## {r.agent_name}\n{r.content}"]
            total_conf += r.confidence
        merged = "\n\n".join(sections)
        consensus = total_conf / len(self._results)
        return AggregatedResult(
            results=self._results,
            merged_content=merged,
            consensus=round(consensus, 4),
        )

    def rank_by_confidence(self) -> list[AgentResult]:
        """Return results sorted by confidence descending."""
        return sorted(self._results, key=lambda r: r.confidence, reverse=True)

    def detect_conflicts(self) -> list[tuple[str, str]]:
        """Return pairs of agents with potentially contradictory results.

        Simple heuristic: results that differ significantly in length
        (more than 3x ratio) are flagged as conflicting.
        """
        conflicts: list[tuple[str, str]] = []
        results = list(self._results)
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                a, b = results[i], results[j]
                len_a, len_b = len(a.content), len(b.content)
                if len_a == 0 and len_b == 0:
                    continue
                ratio = max(len_a, len_b) / max(min(len_a, len_b), 1)
                if ratio > 3.0:
                    conflicts = [*conflicts, (a.agent_name, b.agent_name)]
        return conflicts

    def best(self) -> AgentResult | None:
        """Return highest-confidence result, or None if empty."""
        if not self._results:
            return None
        ranked = self.rank_by_confidence()
        return ranked[0]

    def summary(self) -> str:
        """Human-readable summary."""
        if not self._results:
            return "No results collected."
        merged = self.merge()
        return (
            f"Results: {len(self._results)} agents, "
            f"consensus={merged.consensus:.2f}"
        )
