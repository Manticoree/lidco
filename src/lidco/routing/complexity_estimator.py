"""Estimate task complexity from a user prompt."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_DEFAULT_THRESHOLDS: dict[str, float] = {
    "low": 0.25,
    "medium": 0.50,
    "high": 0.75,
}

_MULTI_STEP_INDICATORS = [
    "then",
    "after that",
    "also",
    "next",
    "finally",
    "additionally",
    "moreover",
    "furthermore",
]

_COMPLEXITY_WORDS = [
    "refactor",
    "architect",
    "design",
    "optimise",
    "optimize",
    "migrate",
    "rewrite",
    "integrate",
    "parallel",
    "distributed",
    "concurrent",
    "security",
    "performance",
]


@dataclass(frozen=True)
class ComplexityResult:
    """Result of a complexity estimation."""

    level: str
    score: float
    factors: list[str] = field(default_factory=list)
    token_estimate: int = 0


class ComplexityEstimator:
    """Estimate task complexity from prompt text and optional tool hints."""

    def __init__(self, thresholds: dict[str, float] | None = None) -> None:
        self._thresholds = dict(thresholds) if thresholds else dict(_DEFAULT_THRESHOLDS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate(
        self,
        prompt: str,
        tool_hints: list[str] | None = None,
    ) -> ComplexityResult:
        """Return a :class:`ComplexityResult` for *prompt*."""
        score = self._score_prompt(prompt)
        if tool_hints:
            score = min(1.0, score + len(tool_hints) * 0.04)
        factors = self._detect_factors(prompt, tool_hints)
        level = self._level_from_score(score)
        token_estimate = max(100, int(len(prompt.split()) * 15 * (1 + score)))
        return ComplexityResult(
            level=level,
            score=round(score, 4),
            factors=factors,
            token_estimate=token_estimate,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_prompt(self, prompt: str) -> float:  # noqa: C901
        score = 0.0
        words = prompt.split()
        # length contribution
        score += min(0.3, len(words) / 500)
        # code block count
        code_blocks = prompt.count("```")
        score += min(0.15, code_blocks * 0.05)
        # file references
        file_refs = len(re.findall(r"[\w/\\]+\.\w{1,5}", prompt))
        score += min(0.15, file_refs * 0.03)
        # multi-step indicators
        lower = prompt.lower()
        multi = sum(1 for ind in _MULTI_STEP_INDICATORS if ind in lower)
        score += min(0.2, multi * 0.05)
        # complexity words
        cw = sum(1 for w in _COMPLEXITY_WORDS if w in lower)
        score += min(0.2, cw * 0.05)
        return min(1.0, score)

    def _detect_factors(
        self,
        prompt: str,
        tool_hints: list[str] | None,
    ) -> list[str]:
        factors: list[str] = []
        lower = prompt.lower()
        words = prompt.split()
        if len(words) > 100:
            factors.append("long_prompt")
        if prompt.count("```") >= 2:
            factors.append("code_blocks")
        file_refs = re.findall(r"[\w/\\]+\.\w{1,5}", prompt)
        if file_refs:
            factors.append("file_references")
        if any(ind in lower for ind in _MULTI_STEP_INDICATORS):
            factors.append("multi_step")
        if any(w in lower for w in _COMPLEXITY_WORDS):
            factors.append("complexity_keywords")
        if tool_hints:
            factors.append("tool_hints")
        return factors

    def _level_from_score(self, score: float) -> str:
        if score < self._thresholds.get("low", 0.25):
            return "low"
        if score < self._thresholds.get("medium", 0.50):
            return "medium"
        if score < self._thresholds.get("high", 0.75):
            return "high"
        return "expert"
