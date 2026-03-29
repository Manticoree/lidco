"""Context Report — measure and visualize context window usage.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass

from lidco.context.token_estimator import TokenEstimator


@dataclass
class ContextUsage:
    """Token usage breakdown for a context window."""
    system_tokens: int
    history_tokens: int
    context_tokens: int
    output_reserved: int
    total: int
    budget: int = 0

    @property
    def utilization(self) -> float:
        """Fraction of budget used (0.0–1.0+)."""
        if not self.budget:
            return 0.0
        return self.total / self.budget


class ContextReport:
    """Measure and format context window usage."""

    BAR_WIDTH = 40

    def __init__(self, budget: int, estimator: TokenEstimator | None = None) -> None:
        self._budget = budget
        self._estimator = estimator or TokenEstimator()

    def measure(self, messages: list[dict]) -> ContextUsage:
        """Measure token usage across message list by role."""
        system_tokens = 0
        history_tokens = 0
        context_tokens = 0

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            tokens = self._estimator.estimate(content if isinstance(content, str) else str(content))
            if role == "system":
                system_tokens += tokens
            elif role in ("user", "assistant"):
                history_tokens += tokens
            else:
                context_tokens += tokens

        # Reserve ~20% for output
        output_reserved = max(256, int(self._budget * 0.2))
        total = system_tokens + history_tokens + context_tokens

        return ContextUsage(
            system_tokens=system_tokens,
            history_tokens=history_tokens,
            context_tokens=context_tokens,
            output_reserved=output_reserved,
            total=total,
            budget=self._budget,
        )

    def format(self, usage: ContextUsage) -> str:
        """Format usage as ASCII bar chart with numbers."""
        util = usage.utilization
        filled = int(util * self.BAR_WIDTH)
        filled = min(filled, self.BAR_WIDTH)
        bar = "█" * filled + "░" * (self.BAR_WIDTH - filled)
        pct = f"{util * 100:.1f}%"
        lines = [
            f"Context Usage: [{bar}] {pct}",
            f"  System  : {usage.system_tokens:>7} tokens",
            f"  History : {usage.history_tokens:>7} tokens",
            f"  Context : {usage.context_tokens:>7} tokens",
            f"  Total   : {usage.total:>7} / {usage.budget} tokens",
            f"  Reserved: {usage.output_reserved:>7} tokens (output)",
        ]
        return "\n".join(lines)

    def is_critical(self, usage: ContextUsage, threshold: float = 0.9) -> bool:
        """Return True if utilization exceeds threshold."""
        return usage.utilization >= threshold
