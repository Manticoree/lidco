"""Score task complexity from prompt text."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Sequence


class Complexity(str, Enum):
    """Task complexity levels."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass(frozen=True)
class TaskScore:
    """Immutable result of scoring a task prompt."""

    complexity: Complexity
    score: float = 0.0
    indicators: tuple[str, ...] = ()
    suggested_max_tokens: int = 4096


_TOKEN_MAP: dict[Complexity, int] = {
    Complexity.SIMPLE: 1024,
    Complexity.MODERATE: 4096,
    Complexity.COMPLEX: 8192,
    Complexity.EXPERT: 16384,
}

_SIMPLE_PATTERNS: Sequence[tuple[str, str]] = (
    (r"\bwhat is\b", "what-is question"),
    (r"\bexplain\b", "explanation request"),
)

_MODERATE_PATTERNS: Sequence[tuple[str, str]] = (
    (r"\bfix\b", "fix request"),
    (r"\bupdate\b", "update request"),
    (r"[a-zA-Z_]\w*\.\w+", "file reference"),
    (r"`[^`]+`", "code mention"),
)

_COMPLEX_PATTERNS: Sequence[tuple[str, str]] = (
    (r"\brefactor\b", "refactor request"),
    (r"\bimplement\b", "implement request"),
    (r"\b(step\s*\d|first.*then|1\).*2\))", "multi-step instructions"),
)

_EXPERT_PATTERNS: Sequence[tuple[str, str]] = (
    (r"\barchitecture\b", "architecture mention"),
    (r"\bdesign\b", "design mention"),
    (r"\brewrite\b", "rewrite request"),
    (r"```", "code block"),
)


class TaskScorer:
    """Analyze a user prompt to estimate task complexity."""

    def __init__(self) -> None:
        self._weights: dict[str, float] = {
            "simple": 0.1,
            "moderate": 0.3,
            "complex": 0.6,
            "expert": 0.9,
        }

    # ------------------------------------------------------------------
    def score(self, prompt: str) -> TaskScore:
        """Return a *TaskScore* for *prompt*."""
        indicators = tuple(self._detect_indicators(prompt))
        raw = self._raw_score(prompt, indicators)
        complexity = self._classify(raw)
        return TaskScore(
            complexity=complexity,
            score=round(raw, 4),
            indicators=indicators,
            suggested_max_tokens=self.suggest_max_tokens(complexity),
        )

    # ------------------------------------------------------------------
    def _detect_indicators(self, prompt: str) -> list[str]:
        found: list[str] = []
        lower = prompt.lower()
        for pat, label in _SIMPLE_PATTERNS:
            if re.search(pat, lower):
                found.append(label)
        for pat, label in _MODERATE_PATTERNS:
            if re.search(pat, lower):
                found.append(label)
        for pat, label in _COMPLEX_PATTERNS:
            if re.search(pat, lower):
                found.append(label)
        for pat, label in _EXPERT_PATTERNS:
            if re.search(pat, prompt):  # case-sensitive for code blocks
                found.append(label)
        # Multiple file paths → complex+
        paths = re.findall(r"[a-zA-Z_]\w*/\w[\w/]*\.\w+", prompt)
        if len(paths) >= 2:
            found.append("multiple file paths")
        return found

    # ------------------------------------------------------------------
    def _raw_score(self, prompt: str, indicators: tuple[str, ...] | list[str]) -> float:
        if not prompt.strip():
            return 0.0
        s = 0.0
        n = 0
        indicator_set = set(indicators)
        for _, label in _EXPERT_PATTERNS:
            if label in indicator_set:
                s += self._weights["expert"]
                n += 1
        if "multiple file paths" in indicator_set:
            s += self._weights["expert"]
            n += 1
        for _, label in _COMPLEX_PATTERNS:
            if label in indicator_set:
                s += self._weights["complex"]
                n += 1
        for _, label in _MODERATE_PATTERNS:
            if label in indicator_set:
                s += self._weights["moderate"]
                n += 1
        for _, label in _SIMPLE_PATTERNS:
            if label in indicator_set:
                s += self._weights["simple"]
                n += 1
        if len(prompt) < 100 and n == 0:
            return 0.1
        return min(s / max(n, 1), 1.0)

    # ------------------------------------------------------------------
    @staticmethod
    def _classify(raw: float) -> Complexity:
        if raw < 0.25:
            return Complexity.SIMPLE
        if raw < 0.5:
            return Complexity.MODERATE
        if raw < 0.75:
            return Complexity.COMPLEX
        return Complexity.EXPERT

    # ------------------------------------------------------------------
    @staticmethod
    def suggest_max_tokens(complexity: Complexity) -> int:
        return _TOKEN_MAP.get(complexity, 4096)

    # ------------------------------------------------------------------
    @staticmethod
    def summary(score: TaskScore) -> str:
        parts = [
            f"Complexity: {score.complexity.value}",
            f"Score: {score.score:.2f}",
            f"Suggested max tokens: {score.suggested_max_tokens}",
        ]
        if score.indicators:
            parts.append(f"Indicators: {', '.join(score.indicators)}")
        return "TaskScore: " + " | ".join(parts)
