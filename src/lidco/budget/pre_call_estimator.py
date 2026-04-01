"""Estimate token cost of a tool call before execution."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostEstimate:
    """Immutable result of a pre-call cost estimate."""

    tool_name: str
    estimated_tokens: int = 0
    confidence: float = 0.5
    within_budget: bool = True
    budget_remaining: int = 0


# Exponential moving average smoothing factor.
_EMA_ALPHA = 0.3


class PreCallEstimator:
    """Estimate token cost of a tool call before execution."""

    def __init__(self, default_estimate: int = 500) -> None:
        self._tool_averages: dict[str, float] = {}
        self._default = default_estimate

    # ------------------------------------------------------------------
    def estimate(
        self,
        tool_name: str,
        args: dict[str, object] | None = None,
        budget_remaining: int = 100_000,
    ) -> CostEstimate:
        """Return a *CostEstimate* for the given tool call."""
        args = args or {}
        est = self._base_estimate(tool_name, args)
        confidence = 0.8 if tool_name in self._tool_averages else 0.5
        return CostEstimate(
            tool_name=tool_name,
            estimated_tokens=est,
            confidence=confidence,
            within_budget=est <= budget_remaining,
            budget_remaining=budget_remaining,
        )

    # ------------------------------------------------------------------
    def _base_estimate(self, tool_name: str, args: dict[str, object]) -> int:
        if tool_name in self._tool_averages:
            return int(self._tool_averages[tool_name])
        lower = tool_name.lower()
        if lower == "read":
            size_hint = args.get("size_hint")
            if isinstance(size_hint, (int, float)) and size_hint > 0:
                return max(100, int(size_hint / 4))
            return 600
        if lower == "grep":
            pattern = args.get("pattern", "")
            return 400 + min(len(str(pattern)) * 10, 400)
        if lower == "bash":
            return 800
        return self._default

    # ------------------------------------------------------------------
    def record_actual(self, tool_name: str, tokens: int) -> None:
        """Update running EMA for *tool_name*."""
        prev = self._tool_averages.get(tool_name)
        if prev is None:
            self._tool_averages = {**self._tool_averages, tool_name: float(tokens)}
        else:
            new_avg = _EMA_ALPHA * tokens + (1 - _EMA_ALPHA) * prev
            self._tool_averages = {**self._tool_averages, tool_name: new_avg}

    # ------------------------------------------------------------------
    def get_average(self, tool_name: str) -> int:
        """Return current average estimate for *tool_name*, or the default."""
        return int(self._tool_averages.get(tool_name, self._default))

    # ------------------------------------------------------------------
    def is_affordable(self, tool_name: str, budget_remaining: int) -> bool:
        """Quick check whether calling *tool_name* fits the remaining budget."""
        est = self.estimate(tool_name, budget_remaining=budget_remaining)
        return est.within_budget

    # ------------------------------------------------------------------
    def summary(self) -> str:
        lines = [f"PreCallEstimator: default={self._default}"]
        for name, avg in sorted(self._tool_averages.items()):
            lines.append(f"  {name}: avg={avg:.0f}")
        if not self._tool_averages:
            lines.append("  (no history)")
        return "\n".join(lines)
