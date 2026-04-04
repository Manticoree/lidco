"""EvidenceLinker — link claims to supporting evidence.

Stdlib only, dataclass results.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvidenceLink:
    """A link between a claim and its supporting evidence."""

    claim: str
    source: str
    content: str
    strength: float  # 0.0 – 1.0


class EvidenceLinker:
    """Maintain an evidence pool and link claims to it."""

    def __init__(self) -> None:
        self._evidence: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # add_evidence
    # ------------------------------------------------------------------
    def add_evidence(self, source: str, content: str) -> None:
        """Register a piece of evidence with its source label."""
        self._evidence.append({"source": source, "content": content})

    # ------------------------------------------------------------------
    # link
    # ------------------------------------------------------------------
    def link(self, claim: str) -> EvidenceLink | None:
        """Find the best matching evidence for *claim*.

        Returns None when no evidence shares significant vocabulary.
        """
        claim_words = {w for w in claim.lower().split() if len(w) >= 3}
        if not claim_words:
            return None

        best: EvidenceLink | None = None
        best_score = 0.0

        for ev in self._evidence:
            ev_words = {w for w in ev["content"].lower().split() if len(w) >= 3}
            if not ev_words:
                continue
            overlap = len(claim_words & ev_words)
            strength = overlap / max(len(claim_words), 1)
            if strength > best_score:
                best_score = strength
                best = EvidenceLink(
                    claim=claim,
                    source=ev["source"],
                    content=ev["content"],
                    strength=round(strength, 4),
                )

        return best if best_score > 0 else None

    # ------------------------------------------------------------------
    # coverage
    # ------------------------------------------------------------------
    def coverage(self, claims: list[str]) -> float:
        """Return fraction of claims that can be linked to evidence."""
        if not claims:
            return 1.0
        linked = sum(1 for c in claims if self.link(c) is not None)
        return round(linked / len(claims), 4)

    # ------------------------------------------------------------------
    # unlinked
    # ------------------------------------------------------------------
    def unlinked(self, claims: list[str]) -> list[str]:
        """Return claims that have no matching evidence."""
        return [c for c in claims if self.link(c) is None]
