"""Adaptive token budgeting — Task 424.

Dynamically adjusts the max_tokens budget for LLM calls based on prompt
complexity and conversation history depth.

Usage::

    budget = AdaptiveBudget(base_budget=4096)
    tokens = budget.compute(prompt, history_length=12)
    budget.record_usage(prompt_tokens=800, completion_tokens=1200)
    print(budget.efficiency_ratio)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CODE_BLOCK_RE = re.compile(r"```[\s\S]+?```|`[^`]+`")
_FILE_REF_RE = re.compile(r"\b\w[\w/\\.-]+\.\w{2,6}\b")
_MULTI_STEP_RE = re.compile(
    r"\b(step\s+\d|first|second|third|then|after\s+that|finally|"
    r"list\s+all|enumerate|compare\s+\w+\s+and)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ComplexityScore:
    """Result of complexity analysis."""

    value: float  # 0.0–1.0
    length: float  # word-count sub-score
    has_code: bool
    has_files: bool
    multi_step: bool

    @property
    def bucket(self) -> str:
        if self.value <= 0.3:
            return "simple"
        if self.value <= 0.6:
            return "medium"
        if self.value <= 0.8:
            return "complex"
        return "deep"

    @property
    def token_budget(self) -> int:
        """Recommended max_tokens for this complexity level."""
        return _BUCKET_BUDGETS[self.bucket]


_BUCKET_BUDGETS: dict[str, int] = {
    "simple": 2000,
    "medium": 4000,
    "complex": 8000,
    "deep": 16000,
}


class TaskComplexityAnalyzer:
    """Scores a prompt's complexity across multiple dimensions."""

    _MAX_WORDS = 400

    def score(self, prompt: str) -> ComplexityScore:
        """Analyse *prompt* and return a :class:`ComplexityScore`."""
        if not prompt or not prompt.strip():
            return ComplexityScore(
                value=0.0,
                length=0.0,
                has_code=False,
                has_files=False,
                multi_step=False,
            )

        words = prompt.split()
        word_count = len(words)

        # Length sub-score (0–0.4)
        length_score = min(0.4, (word_count / self._MAX_WORDS) * 0.4)

        # Code presence (0 or 0.25)
        code_blocks = _CODE_BLOCK_RE.findall(prompt)
        has_code = bool(code_blocks)
        code_score = 0.25 if has_code else 0.0

        # File references (0 or 0.15)
        file_refs = _FILE_REF_RE.findall(prompt)
        has_files = len(file_refs) >= 2
        file_score = 0.15 if has_files else 0.0

        # Multi-step indicators (0 or 0.20)
        multi_step = bool(_MULTI_STEP_RE.search(prompt))
        step_score = 0.20 if multi_step else 0.0

        total = min(1.0, length_score + code_score + file_score + step_score)

        return ComplexityScore(
            value=total,
            length=length_score,
            has_code=has_code,
            has_files=has_files,
            multi_step=multi_step,
        )


class AdaptiveBudget:
    """Adapts max_tokens based on prompt complexity and conversation depth.

    Args:
        base_budget: Default/fallback token budget when adaptation is minimal.
    """

    _DEPTH_SCALE = 0.1  # +10% per 10 history turns, capped at +30%
    _MAX_DEPTH_BONUS = 0.30
    _MIN_BUDGET = 512
    _MAX_BUDGET = 32000

    def __init__(self, base_budget: int = 4096) -> None:
        self.base_budget = base_budget
        self._analyzer = TaskComplexityAnalyzer()
        self._total_budgeted: int = 0
        self._total_completion: int = 0
        self._call_count: int = 0

    def compute(self, prompt: str, history_length: int = 0) -> int:
        """Return an adjusted max_tokens value.

        Args:
            prompt: The user prompt to analyse.
            history_length: Number of messages in the conversation so far.

        Returns:
            Integer token budget, clamped to [_MIN_BUDGET, _MAX_BUDGET].
        """
        cs = self._analyzer.score(prompt)
        base = cs.token_budget

        # Depth bonus: deeper conversations may need more tokens
        depth_bonus = min(
            self._MAX_DEPTH_BONUS,
            (history_length // 10) * self._DEPTH_SCALE,
        )
        adjusted = int(base * (1.0 + depth_bonus))

        return max(self._MIN_BUDGET, min(self._MAX_BUDGET, adjusted))

    def record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Track actual token usage for efficiency measurement."""
        if completion_tokens > 0:
            self._total_budgeted += completion_tokens + prompt_tokens
            self._total_completion += completion_tokens
            self._call_count += 1

    @property
    def efficiency_ratio(self) -> float:
        """Ratio of completion tokens to budgeted tokens.

        Values close to 1.0 indicate the budget is well-utilised.
        Returns 0.0 if no usage has been recorded.
        """
        if self._total_budgeted == 0:
            return 0.0
        return self._total_completion / self._total_budgeted

    @property
    def call_count(self) -> int:
        """Number of recorded usage events."""
        return self._call_count
