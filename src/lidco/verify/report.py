"""VerificationReport — generate comprehensive verification reports.

Stdlib only, dataclass results.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReportSection:
    """One section of a verification report."""

    name: str
    findings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReportResult:
    """Full verification report output."""

    sections: list[ReportSection]
    score: float
    recommendations: list[str]


class VerificationReport:
    """Build and generate a verification report."""

    def __init__(self) -> None:
        self._sections: list[ReportSection] = []
        self._claims: list[str] = []

    # ------------------------------------------------------------------
    # add_section
    # ------------------------------------------------------------------
    def add_section(self, name: str, findings: list[str]) -> None:
        """Append a named section with its findings."""
        self._sections.append(ReportSection(name=name, findings=list(findings)))

    # ------------------------------------------------------------------
    # add_claim
    # ------------------------------------------------------------------
    def add_claim(self, claim: str) -> None:
        """Register a claim that requires verification."""
        self._claims.append(claim)

    # ------------------------------------------------------------------
    # confidence_score
    # ------------------------------------------------------------------
    def confidence_score(self) -> float:
        """Compute an overall confidence score (0.0–1.0).

        Based on: ratio of sections with no issues + claim coverage.
        """
        if not self._sections:
            return 0.0
        clean = sum(
            1 for s in self._sections if not s.findings
        )
        section_score = clean / len(self._sections)

        if self._claims:
            verified = sum(
                1 for c in self._claims
                if any(
                    c.lower() in f.lower()
                    for s in self._sections
                    for f in s.findings
                )
            )
            claim_score = verified / len(self._claims)
        else:
            claim_score = 1.0

        return round((section_score + claim_score) / 2, 4)

    # ------------------------------------------------------------------
    # unverified_claims
    # ------------------------------------------------------------------
    def unverified_claims(self) -> list[str]:
        """Return claims not mentioned in any section finding."""
        all_findings = " ".join(
            f.lower() for s in self._sections for f in s.findings
        )
        return [
            c for c in self._claims if c.lower() not in all_findings
        ]

    # ------------------------------------------------------------------
    # generate
    # ------------------------------------------------------------------
    def generate(self) -> ReportResult:
        """Produce the final ReportResult."""
        score = self.confidence_score()
        recommendations: list[str] = []

        unverified = self.unverified_claims()
        if unverified:
            recommendations.append(
                f"Verify {len(unverified)} unverified claim(s): "
                + ", ".join(unverified)
            )

        for section in self._sections:
            if section.findings:
                recommendations.append(
                    f"Address {len(section.findings)} finding(s) in '{section.name}'"
                )

        if score < 0.5:
            recommendations.append("Overall confidence is low; review reasoning chain")

        return ReportResult(
            sections=list(self._sections),
            score=score,
            recommendations=recommendations,
        )
