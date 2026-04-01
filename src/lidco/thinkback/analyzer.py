"""Analyze thinking trace for key decisions and confidence."""
from __future__ import annotations

from dataclasses import dataclass, field
import re

_DECISION_PATTERNS = re.compile(
    r"(?i)\b(I'll|I should|let me|decision:|therefore)\b"
)
_UNCERTAINTY_PATTERNS = re.compile(
    r"(?i)\b(maybe|not sure|could be|uncertain|possibly|might be)\b"
)


@dataclass(frozen=True)
class Decision:
    """A single extracted decision."""

    text: str
    turn: int = 0
    confidence: float = 0.5
    category: str = ""


@dataclass(frozen=True)
class AnalysisResult:
    """Result of analyzing a thinking block."""

    decisions: tuple[Decision, ...] = ()
    uncertainties: tuple[str, ...] = ()
    chain_length: int = 0
    summary_text: str = ""


class ThinkingAnalyzer:
    """Extract decisions, uncertainty, and confidence from thinking."""

    def __init__(self) -> None:
        self._analyses_count: int = 0

    def analyze(self, content: str, turn: int = 0) -> AnalysisResult:
        """Full analysis of a thinking block."""
        self._analyses_count += 1
        decisions = self.extract_decisions(content, turn)
        uncertainties = self.detect_uncertainty(content)
        chain_length = len(decisions)
        summary_text = self.summarize_chain(content)
        return AnalysisResult(
            decisions=tuple(decisions),
            uncertainties=tuple(uncertainties),
            chain_length=chain_length,
            summary_text=summary_text,
        )

    def extract_decisions(self, content: str, turn: int = 0) -> list[Decision]:
        """Extract decision lines from content."""
        results: list[Decision] = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _DECISION_PATTERNS.search(stripped):
                confidence = self.confidence_score(stripped)
                category = self._categorize(stripped)
                results.append(
                    Decision(
                        text=stripped,
                        turn=turn,
                        confidence=confidence,
                        category=category,
                    )
                )
        return results

    def detect_uncertainty(self, content: str) -> list[str]:
        """Return lines containing uncertainty markers."""
        results: list[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and _UNCERTAINTY_PATTERNS.search(stripped):
                results.append(stripped)
        return results

    def confidence_score(self, content: str) -> float:
        """Compute 0.0-1.0 confidence; lower with more uncertainty."""
        matches = _UNCERTAINTY_PATTERNS.findall(content)
        penalty = len(matches) * 0.15
        return max(0.0, min(1.0, 1.0 - penalty))

    def summarize_chain(self, content: str) -> str:
        """Return first + last decision sentences."""
        decisions = self.extract_decisions(content)
        if not decisions:
            return ""
        if len(decisions) == 1:
            return decisions[0].text
        return f"{decisions[0].text} ... {decisions[-1].text}"

    def summary(self) -> str:
        """Summary of analyzer usage."""
        return f"ThinkingAnalyzer: {self._analyses_count} analyses performed"

    # ------------------------------------------------------------------

    @staticmethod
    def _categorize(text: str) -> str:
        lower = text.lower()
        if "therefore" in lower or "decision:" in lower:
            return "conclusion"
        if "let me" in lower:
            return "exploration"
        return "intention"
