"""KnowledgeBoundary — detect questions near knowledge limits."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BoundaryAssessment:
    """Assessment of whether a question is within knowledge boundaries."""

    query: str
    within_boundary: bool
    confidence: float  # 0-1
    category: str  # "known", "uncertain", "unknown"
    verification_steps: list[str] = field(default_factory=list)
    suggested_sources: list[str] = field(default_factory=list)


class KnowledgeBoundary:
    """Detect questions near knowledge limits and suggest verification."""

    def __init__(self) -> None:
        self._known_domains: set[str] = set()
        self._uncertain_patterns: list[str] = []
        self._assessments: list[BoundaryAssessment] = []

    def add_known_domain(self, domain: str) -> None:
        """Register a known domain of expertise."""
        self._known_domains.add(domain.lower())

    def add_uncertain_pattern(self, pattern: str) -> None:
        """Add a pattern that triggers uncertainty."""
        self._uncertain_patterns.append(pattern.lower())

    def assess(self, query: str) -> BoundaryAssessment:
        """Assess whether a query is within knowledge boundaries."""
        query_lower = query.lower()
        words = set(query_lower.split())

        # Check known domains
        domain_matches = sum(1 for d in self._known_domains if d in query_lower)
        # Check uncertain patterns
        uncertain_matches = sum(1 for p in self._uncertain_patterns if p in query_lower)

        if domain_matches > 0 and uncertain_matches == 0:
            category = "known"
            confidence = min(0.7 + domain_matches * 0.1, 1.0)
            within = True
            verification = []
            sources = []
        elif uncertain_matches > 0:
            category = "uncertain"
            confidence = max(0.3 - uncertain_matches * 0.05, 0.1)
            within = False
            verification = ["Verify with authoritative source", "Cross-check facts"]
            sources = ["Documentation", "Expert consultation"]
        else:
            category = "unknown"
            confidence = 0.2
            within = False
            verification = ["Research the topic", "Check official docs"]
            sources = ["Web search", "Documentation"]

        # Time-sensitive queries reduce confidence
        time_markers = ["latest", "current", "today", "now", "recent", "2026", "2027"]
        if any(m in query_lower for m in time_markers):
            confidence = max(confidence - 0.2, 0.1)
            if "Verify current information" not in verification:
                verification.insert(0, "Verify current information")

        assessment = BoundaryAssessment(
            query=query,
            within_boundary=within,
            confidence=round(confidence, 3),
            category=category,
            verification_steps=verification,
            suggested_sources=sources,
        )
        self._assessments.append(assessment)
        return assessment

    def history(self) -> list[BoundaryAssessment]:
        return list(self._assessments)

    def uncertain_ratio(self) -> float:
        """Fraction of assessments that were uncertain or unknown."""
        if not self._assessments:
            return 0.0
        uncertain = sum(1 for a in self._assessments if not a.within_boundary)
        return round(uncertain / len(self._assessments), 3)

    def summary(self) -> dict:
        return {
            "known_domains": len(self._known_domains),
            "uncertain_patterns": len(self._uncertain_patterns),
            "assessments": len(self._assessments),
            "uncertain_ratio": self.uncertain_ratio(),
        }
