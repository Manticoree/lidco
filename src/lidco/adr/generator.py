"""ADR Generator — auto-generate ADRs from discussions and context.

Extracts context, decision, and consequences from free-form text,
producing structured ADRs in markdown format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lidco.adr.manager import ADR, ADRManager, ADRStatus


@dataclass
class DiscussionEntry:
    """A single discussion point or comment."""

    author: str
    content: str
    timestamp: str = ""
    role: str = ""  # e.g. "architect", "developer", "reviewer"

    def to_dict(self) -> dict[str, Any]:
        return {
            "author": self.author,
            "content": self.content,
            "timestamp": self.timestamp,
            "role": self.role,
        }


@dataclass
class GenerationResult:
    """Result of ADR generation."""

    adr: ADR
    extracted_context: str
    extracted_decision: str
    extracted_consequences: str
    confidence: float = 0.0
    source_entries: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "adr": self.adr.to_dict(),
            "extracted_context": self.extracted_context,
            "extracted_decision": self.extracted_decision,
            "extracted_consequences": self.extracted_consequences,
            "confidence": self.confidence,
            "source_entries": self.source_entries,
        }


# Keyword patterns for section extraction
_CONTEXT_KEYWORDS = [
    "because", "since", "given that", "the problem", "we need",
    "currently", "requirement", "constraint", "issue", "challenge",
]
_DECISION_KEYWORDS = [
    "we will", "we decided", "the decision", "we chose", "approach",
    "solution", "we adopt", "we use", "selected", "going with",
]
_CONSEQUENCE_KEYWORDS = [
    "consequence", "impact", "trade-off", "tradeoff", "downside",
    "benefit", "risk", "result", "effect", "implication",
]


def _score_sentence(sentence: str, keywords: list[str]) -> float:
    """Score a sentence based on keyword matches."""
    lower = sentence.lower()
    hits = sum(1 for kw in keywords if kw in lower)
    return hits / max(len(keywords), 1)


def _extract_section(entries: list[DiscussionEntry], keywords: list[str]) -> str:
    """Extract relevant sentences from discussion entries for a section."""
    scored: list[tuple[float, str]] = []
    for entry in entries:
        sentences = re.split(r'[.!?]+', entry.content)
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            score = _score_sentence(s, keywords)
            if score > 0:
                scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for _, s in scored[:5]]
    return ". ".join(top) + "." if top else ""


def _extract_title(entries: list[DiscussionEntry]) -> str:
    """Extract a title from discussion entries."""
    if not entries:
        return "Untitled Decision"
    # Use first entry's first sentence as title basis
    first_content = entries[0].content.strip()
    first_sentence = re.split(r'[.!?\n]+', first_content)[0].strip()
    # Cap length
    if len(first_sentence) > 80:
        first_sentence = first_sentence[:77] + "..."
    return first_sentence or "Untitled Decision"


def _compute_confidence(context: str, decision: str, consequences: str) -> float:
    """Compute confidence score based on extraction quality."""
    score = 0.0
    if context:
        score += 0.35
    if decision:
        score += 0.40
    if consequences:
        score += 0.25
    # Bonus for length (more content = more confident)
    total_len = len(context) + len(decision) + len(consequences)
    if total_len > 200:
        score = min(score + 0.1, 1.0)
    return round(score, 2)


class ADRGenerator:
    """Generate ADRs from discussions and free-form text."""

    def __init__(self, manager: ADRManager | None = None) -> None:
        self._manager = manager or ADRManager()

    @property
    def manager(self) -> ADRManager:
        return self._manager

    def generate_from_discussion(
        self,
        entries: list[DiscussionEntry],
        *,
        title: str = "",
        authors: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> GenerationResult:
        """Generate an ADR from a list of discussion entries."""
        if not entries:
            raise ValueError("At least one discussion entry is required")

        extracted_context = _extract_section(entries, _CONTEXT_KEYWORDS)
        extracted_decision = _extract_section(entries, _DECISION_KEYWORDS)
        extracted_consequences = _extract_section(entries, _CONSEQUENCE_KEYWORDS)

        if not title:
            title = _extract_title(entries)

        resolved_authors = authors
        if not resolved_authors:
            resolved_authors = list({e.author for e in entries if e.author})

        confidence = _compute_confidence(
            extracted_context, extracted_decision, extracted_consequences,
        )

        adr = self._manager.create(
            title=title,
            context=extracted_context,
            decision=extracted_decision,
            consequences=extracted_consequences,
            authors=resolved_authors,
            tags=tags,
        )

        return GenerationResult(
            adr=adr,
            extracted_context=extracted_context,
            extracted_decision=extracted_decision,
            extracted_consequences=extracted_consequences,
            confidence=confidence,
            source_entries=len(entries),
        )

    def generate_from_text(
        self,
        text: str,
        *,
        title: str = "",
        author: str = "",
        tags: list[str] | None = None,
    ) -> GenerationResult:
        """Generate an ADR from free-form text."""
        if not text.strip():
            raise ValueError("Text must not be empty")
        entry = DiscussionEntry(author=author, content=text)
        return self.generate_from_discussion(
            [entry], title=title, authors=[author] if author else None, tags=tags,
        )

    def generate_markdown(self, result: GenerationResult) -> str:
        """Render a generation result as markdown."""
        return result.adr.to_markdown()
