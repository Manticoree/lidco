"""Session-level token budget tracking."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Pricing in USD per million tokens: {model_substr: (input, output)}
# Used as fallback when litellm returns 0.0 for a model (e.g. custom providers).
COST_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    # Z.AI / GLM models (approximate public pricing)
    "glm-4.7-flash": (0.14, 0.14),
    "glm-4.7": (0.57, 0.57),
    "glm-4.5-air": (0.14, 0.14),
    "glm-4.5": (0.57, 0.57),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    # Anthropic Claude
    "claude-haiku": (0.25, 1.25),
    "claude-sonnet": (3.00, 15.00),
    "claude-opus": (15.00, 75.00),
    # Ollama / local (free)
    "ollama/": (0.0, 0.0),
}


def estimate_cost_from_tokens(
    model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """Estimate cost using COST_PER_MILLION_TOKENS lookup.

    Tries longest-matching substring so ``openai/glm-4.7-flash`` matches
    ``glm-4.7-flash`` before ``glm-4.7``.

    Returns 0.0 if the model is not in the table.
    """
    model_lower = model.lower()
    # Sort by key length descending so longer (more specific) patterns match first
    for key, (input_price, output_price) in sorted(
        COST_PER_MILLION_TOKENS.items(), key=lambda kv: -len(kv[0])
    ):
        if key in model_lower:
            return (
                prompt_tokens * input_price / 1_000_000
                + completion_tokens * output_price / 1_000_000
            )
    return 0.0


class TokenBudgetExceeded(Exception):
    """Raised when the session token budget is exhausted.

    Attributes:
        used:  Total tokens consumed so far.
        limit: The configured session token limit.
    """

    def __init__(self, used: int, limit: int) -> None:
        super().__init__(
            f"Session token budget exhausted: {used:,} / {limit:,} tokens used. "
            "Use /budget to check usage or increase the limit in config."
        )
        self.used = used
        self.limit = limit


@dataclass
class TokenBudget:
    """Tracks cumulative token usage across a session.

    Provides warnings when approaching limits and per-role usage breakdown.
    """

    session_limit: int = 0  # 0 = unlimited
    warning_threshold: float = 0.8  # warn at 80% of limit

    # Internal tracking (mutable — tracks running totals)
    _total_tokens: int = field(default=0, init=False, repr=False)
    _total_prompt_tokens: int = field(default=0, init=False, repr=False)
    _total_completion_tokens: int = field(default=0, init=False, repr=False)
    _total_cost_usd: float = field(default=0.0, init=False, repr=False)
    _by_role: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _cost_by_role: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _warning_callback: object = field(default=None, init=False, repr=False)

    def set_warning_callback(self, callback: object) -> None:
        """Set callback(message: str) invoked when approaching limit."""
        self._warning_callback = callback

    def record(
        self,
        tokens: int,
        role: str = "default",
        cost_usd: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Record token usage and cost for a role."""
        self._total_tokens += tokens
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._by_role[role] = self._by_role.get(role, 0) + tokens
        self._total_cost_usd += cost_usd
        if cost_usd > 0:
            self._cost_by_role[role] = self._cost_by_role.get(role, 0.0) + cost_usd

        if self.session_limit > 0:
            usage_ratio = self._total_tokens / self.session_limit
            if usage_ratio >= 1.0:
                self._warn(
                    f"Token budget exhausted: {self._total_tokens}/{self.session_limit} "
                    f"({usage_ratio:.0%})"
                )
            elif usage_ratio >= self.warning_threshold:
                self._warn(
                    f"Token budget at {usage_ratio:.0%}: "
                    f"{self._total_tokens}/{self.session_limit}"
                )

    def _warn(self, message: str) -> None:
        logger.warning(message)
        if self._warning_callback and callable(self._warning_callback):
            self._warning_callback(message)

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def total_prompt_tokens(self) -> int:
        return self._total_prompt_tokens

    @property
    def total_completion_tokens(self) -> int:
        return self._total_completion_tokens

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost_usd

    @property
    def by_role(self) -> dict[str, int]:
        return dict(self._by_role)

    @property
    def cost_by_role(self) -> dict[str, float]:
        return dict(self._cost_by_role)

    @property
    def remaining(self) -> int | None:
        """Remaining tokens, or None if unlimited."""
        if self.session_limit <= 0:
            return None
        return max(0, self.session_limit - self._total_tokens)

    @property
    def is_exhausted(self) -> bool:
        """True if session limit is set and reached."""
        if self.session_limit <= 0:
            return False
        return self._total_tokens >= self.session_limit

    def check_remaining(self) -> None:
        """Raise :class:`TokenBudgetExceeded` if the budget is exhausted.

        Call this before each agent invocation to prevent new calls when the
        session limit has been reached.  Does nothing when no limit is set
        (``session_limit == 0``).
        """
        if self.is_exhausted:
            raise TokenBudgetExceeded(self._total_tokens, self.session_limit)

    def summary(self) -> str:
        """Human-readable usage summary."""
        cost_str = f" (${self._total_cost_usd:.4f})" if self._total_cost_usd > 0 else ""
        parts = [f"Total: {self._total_tokens} tokens{cost_str}"]
        if self.session_limit > 0:
            remaining = self.remaining or 0
            parts.append(f"Limit: {self.session_limit} (remaining: {remaining})")
        if self._by_role:
            breakdown = ", ".join(f"{r}: {t}" for r, t in sorted(self._by_role.items()))
            parts.append(f"By role: {breakdown}")
        return " | ".join(parts)

    def reset(self) -> None:
        """Reset all counters."""
        self._total_tokens = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_cost_usd = 0.0
        self._by_role.clear()
        self._cost_by_role.clear()
