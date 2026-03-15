"""Extended thinking support — Task 423.

Provides ThinkingConfig, ComplexityEstimator, and ThinkingAdapter for
injecting Anthropic extended-thinking blocks into LLM requests when the
model supports it.

Usage::

    adapter = ThinkingAdapter(ThinkingConfig(enabled=True, budget_tokens=8000))
    params = adapter.inject({"model": "claude-sonnet-4-6", "max_tokens": 4096})
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Models that support extended thinking
_THINKING_MODELS: frozenset[str] = frozenset({
    "claude-3-7",
    "claude-sonnet-4-6",
    "claude-3-7-sonnet",
    "claude-3-7-sonnet-20250219",
    "anthropic/claude-3-7",
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-3-7-sonnet",
    "anthropic/claude-3-7-sonnet-20250219",
    "claude-3-7-sonnet-latest",
    "anthropic/claude-3-7-sonnet-latest",
})

_COMPLEXITY_MARKERS: tuple[str, ...] = (
    "explain", "why", "how", "compare", "design", "architect",
    "analyze", "analyse", "refactor", "implement", "optimize",
    "debug", "trace", "intricate", "complex", "comprehensive",
    "detailed", "step by step", "step-by-step",
)

_CODE_BLOCK_RE = re.compile(r"```[\s\S]+?```|`[^`]+`")
_FILE_PATH_RE = re.compile(r"\b\w[\w/\\.-]+\.\w{2,6}\b")


@dataclass
class ThinkingConfig:
    """Configuration for extended thinking."""

    enabled: bool = False
    budget_tokens: int = 10000
    min_complexity_score: float = 0.7


@dataclass
class ComplexityEstimator:
    """Estimates prompt complexity as a score in [0, 1].

    Heuristics used:
    - word count (longer → more complex)
    - question/analysis complexity markers
    - presence of code blocks
    - file path references
    """

    word_count_threshold: int = 100
    max_word_count: int = 500

    def estimate(self, prompt: str) -> float:
        """Return a complexity score in [0.0, 1.0].

        Higher values indicate that extended thinking is more beneficial.
        """
        if not prompt or not prompt.strip():
            return 0.0

        score = 0.0

        # Word count contribution (up to 0.35)
        words = prompt.split()
        word_count = len(words)
        if word_count >= self.max_word_count:
            score += 0.35
        elif word_count > self.word_count_threshold:
            ratio = (word_count - self.word_count_threshold) / (
                self.max_word_count - self.word_count_threshold
            )
            score += 0.35 * ratio
        else:
            score += 0.05 * min(word_count / self.word_count_threshold, 1.0)

        # Complexity marker contribution (up to 0.30)
        lower = prompt.lower()
        marker_hits = sum(1 for m in _COMPLEXITY_MARKERS if m in lower)
        score += min(0.30, marker_hits * 0.06)

        # Code block contribution (up to 0.20)
        code_blocks = _CODE_BLOCK_RE.findall(prompt)
        code_len = sum(len(b) for b in code_blocks)
        if code_len > 500:
            score += 0.20
        elif code_len > 0:
            score += 0.10

        # File path contribution (up to 0.15)
        file_refs = _FILE_PATH_RE.findall(prompt)
        if len(file_refs) >= 3:
            score += 0.15
        elif file_refs:
            score += 0.07

        return min(1.0, score)


@dataclass
class ThinkingAdapter:
    """Wraps LLM call parameters to inject an extended-thinking block.

    When the model supports thinking and the config is enabled, adds
    ``{"type": "thinking", "budget_tokens": N}`` to the request params.
    """

    config: ThinkingConfig = field(default_factory=ThinkingConfig)
    _estimator: ComplexityEstimator = field(
        default_factory=ComplexityEstimator, init=False, repr=False
    )

    def supports_thinking(self, model: str) -> bool:
        """Return True if the model supports extended thinking."""
        if not model:
            return False
        model_lower = model.lower()
        return any(t in model_lower for t in _THINKING_MODELS)

    def should_activate(self, prompt: str, model: str) -> bool:
        """Return True if thinking should be activated for this call."""
        if not self.config.enabled:
            return False
        if not self.supports_thinking(model):
            return False
        score = self._estimator.estimate(prompt)
        return score >= self.config.min_complexity_score

    def inject(self, params: dict, prompt: str = "") -> dict:
        """Return a new params dict with thinking injected if appropriate.

        Args:
            params: Original LLM call parameters (not mutated).
            prompt: The user prompt for complexity estimation.

        Returns:
            A copy of *params* with ``thinking`` key added when applicable.
        """
        model = params.get("model", "")
        if not self.should_activate(prompt, model):
            return dict(params)

        updated = dict(params)
        updated["thinking"] = {
            "type": "thinking",
            "budget_tokens": self.config.budget_tokens,
        }
        return updated

    def inject_unconditional(self, params: dict) -> dict:
        """Inject thinking block regardless of complexity score.

        Used when the caller has already decided thinking should be active.
        """
        model = params.get("model", "")
        if not self.config.enabled or not self.supports_thinking(model):
            return dict(params)
        updated = dict(params)
        updated["thinking"] = {
            "type": "thinking",
            "budget_tokens": self.config.budget_tokens,
        }
        return updated
