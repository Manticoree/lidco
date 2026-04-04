"""GroundingEngine — ground responses in evidence with source citations."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Citation:
    """A source citation for a claim."""

    claim: str
    source: str  # file path, URL, etc.
    line_range: tuple[int, int] | None = None
    snippet: str = ""
    confidence: float = 0.5


@dataclass
class GroundingResult:
    """Result of grounding analysis."""

    total_claims: int
    grounded_claims: int
    ungrounded_claims: int
    citations: list[Citation] = field(default_factory=list)
    traceability_score: float = 0.0


class GroundingEngine:
    """Ground AI responses in evidence with source citations."""

    def __init__(self) -> None:
        self._sources: dict[str, str] = {}  # source_id -> content
        self._results: list[GroundingResult] = []

    def add_source(self, source_id: str, content: str) -> None:
        """Register a source document for grounding."""
        self._sources[source_id] = content

    def remove_source(self, source_id: str) -> bool:
        if source_id in self._sources:
            del self._sources[source_id]
            return True
        return False

    def sources(self) -> list[str]:
        return list(self._sources.keys())

    def ground_claim(self, claim: str) -> Citation | None:
        """Find evidence for a single claim in registered sources."""
        claim_words = set(claim.lower().split())
        if not claim_words:
            return None

        best_source = None
        best_score = 0.0
        best_snippet = ""

        for source_id, content in self._sources.items():
            content_lower = content.lower()
            # Simple word overlap scoring
            content_words = set(content_lower.split())
            overlap = len(claim_words & content_words)
            score = overlap / max(len(claim_words), 1)

            if score > best_score:
                best_score = score
                best_source = source_id
                # Extract a relevant snippet
                for line in content.split("\n"):
                    line_words = set(line.lower().split())
                    if claim_words & line_words:
                        best_snippet = line.strip()[:200]
                        break

        if best_source and best_score > 0.3:
            return Citation(
                claim=claim,
                source=best_source,
                snippet=best_snippet,
                confidence=round(min(best_score, 1.0), 3),
            )
        return None

    def ground(self, claims: list[str]) -> GroundingResult:
        """Ground a list of claims against registered sources."""
        citations: list[Citation] = []
        grounded = 0
        ungrounded = 0

        for claim in claims:
            citation = self.ground_claim(claim)
            if citation:
                citations.append(citation)
                grounded += 1
            else:
                ungrounded += 1

        total = len(claims)
        traceability = grounded / total if total > 0 else 0.0

        result = GroundingResult(
            total_claims=total,
            grounded_claims=grounded,
            ungrounded_claims=ungrounded,
            citations=citations,
            traceability_score=round(traceability, 3),
        )
        self._results.append(result)
        return result

    def history(self) -> list[GroundingResult]:
        return list(self._results)

    def summary(self) -> dict:
        return {
            "sources": len(self._sources),
            "checks": len(self._results),
            "avg_traceability": round(
                sum(r.traceability_score for r in self._results) / len(self._results), 3
            ) if self._results else 0.0,
        }
