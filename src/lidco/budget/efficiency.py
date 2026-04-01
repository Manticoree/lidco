"""Score session efficiency and identify waste patterns."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EfficiencyScore:
    """Immutable efficiency measurement for a session."""

    score: float = 0.0
    useful_tokens: int = 0
    total_tokens: int = 0
    waste_tokens: int = 0
    waste_patterns: tuple[str, ...] = ()
    grade: str = "C"


def _compute_grade(score: float) -> str:
    """Map a 0-1 score to a letter grade."""
    if score > 0.8:
        return "A"
    if score > 0.6:
        return "B"
    if score > 0.4:
        return "C"
    if score > 0.2:
        return "D"
    return "F"


class EfficiencyScorer:
    """Compute and track efficiency scores for sessions."""

    def __init__(self) -> None:
        self._scores: list[EfficiencyScore] = []

    def score(
        self,
        total_tokens: int,
        useful_tokens: int = 0,
        compaction_savings: int = 0,
        tool_waste: int = 0,
    ) -> EfficiencyScore:
        """Score a session's token efficiency.

        If *useful_tokens* is 0 it is estimated as
        total - tool_waste - compaction_savings.
        """
        if total_tokens <= 0:
            result = EfficiencyScore(
                score=0.0,
                useful_tokens=0,
                total_tokens=0,
                waste_tokens=0,
                grade="F",
            )
            self._scores = [*self._scores, result]
            return result

        if useful_tokens == 0:
            useful_tokens = max(0, total_tokens - tool_waste - compaction_savings)

        raw_score = useful_tokens / total_tokens if total_tokens > 0 else 0.0
        raw_score = min(1.0, max(0.0, raw_score))
        waste = total_tokens - useful_tokens

        patterns: list[str] = []
        if total_tokens > 0 and tool_waste / total_tokens > 0.3:
            patterns.append("excessive tool calls")
        if total_tokens > 0 and compaction_savings / total_tokens < 0.1:
            patterns.append("insufficient compaction")

        grade = _compute_grade(raw_score)
        result = EfficiencyScore(
            score=round(raw_score, 4),
            useful_tokens=useful_tokens,
            total_tokens=total_tokens,
            waste_tokens=waste,
            waste_patterns=tuple(patterns),
            grade=grade,
        )
        self._scores = [*self._scores, result]
        return result

    def rank(self, scores: list[EfficiencyScore]) -> list[EfficiencyScore]:
        """Return *scores* sorted by score descending."""
        return sorted(scores, key=lambda s: s.score, reverse=True)

    def identify_waste(self, tool_tokens: dict[str, int], total: int) -> list[str]:
        """Flag tools consuming >20% of the token budget."""
        if total <= 0:
            return []
        return [
            f"{name} ({tokens} tokens, {tokens * 100 // total}%)"
            for name, tokens in tool_tokens.items()
            if tokens / total > 0.2
        ]

    def summary(self, score_obj: EfficiencyScore) -> str:
        """Human-readable summary of an efficiency score."""
        parts = [
            f"Grade: {score_obj.grade} ({score_obj.score:.2f})",
            f"Useful: {score_obj.useful_tokens}/{score_obj.total_tokens} tokens",
            f"Waste: {score_obj.waste_tokens} tokens",
        ]
        if score_obj.waste_patterns:
            parts.append(f"Patterns: {', '.join(score_obj.waste_patterns)}")
        return " | ".join(parts)
