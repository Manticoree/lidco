"""Dynamically scale max_tokens based on task complexity."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScaleConfig:
    """Configuration for dynamic token scaling."""

    min_tokens: int = 512
    max_tokens: int = 16384
    default_tokens: int = 4096
    learning_rate: float = 0.1


@dataclass(frozen=True)
class ScaleDecision:
    """Immutable result of a scaling decision."""

    requested: int = 0
    adjusted: int = 0
    reason: str = ""
    complexity_score: float = 0.0


class DynamicScaler:
    """Scale token budgets based on complexity and usage history."""

    def __init__(self, config: ScaleConfig | None = None) -> None:
        self._config = config or ScaleConfig()
        self._history: list[tuple[int, int]] = []

    # ------------------------------------------------------------------
    def scale(self, complexity_score: float, base_tokens: int = 4096) -> ScaleDecision:
        """Return a *ScaleDecision* with clamped adjusted tokens."""
        if complexity_score < 0.25:
            factor = 0.25
        elif complexity_score < 0.5:
            factor = 1.0
        elif complexity_score < 0.75:
            factor = 2.0
        else:
            factor = 4.0

        raw = int(base_tokens * factor)
        adjusted = max(self._config.min_tokens, min(raw, self._config.max_tokens))
        return ScaleDecision(
            requested=base_tokens,
            adjusted=adjusted,
            reason=f"factor={factor}x, clamped [{self._config.min_tokens}, {self._config.max_tokens}]",
            complexity_score=complexity_score,
        )

    # ------------------------------------------------------------------
    def record_actual(self, requested: int, used: int) -> None:
        """Log a (requested, actually used) pair for learning."""
        self._history = [*self._history, (requested, used)]

    # ------------------------------------------------------------------
    def average_utilization(self) -> float:
        """Return average actual/requested ratio (0.0 when no history)."""
        if not self._history:
            return 0.0
        ratios = [used / req for req, used in self._history if req > 0]
        return sum(ratios) / len(ratios) if ratios else 0.0

    # ------------------------------------------------------------------
    def adjust_from_history(self, base: int) -> int:
        """Shrink or grow *base* according to historical utilization."""
        util = self.average_utilization()
        if util == 0.0:
            return base
        lr = self._config.learning_rate
        if util < 0.5:
            adjusted = int(base * (1.0 - lr))
        elif util > 0.9:
            adjusted = int(base * (1.0 + lr))
        else:
            adjusted = base
        return max(self._config.min_tokens, min(adjusted, self._config.max_tokens))

    # ------------------------------------------------------------------
    def summary(self) -> str:
        util = self.average_utilization()
        return (
            f"DynamicScaler: history={len(self._history)} samples, "
            f"avg utilization={util:.1%}, "
            f"range=[{self._config.min_tokens}, {self._config.max_tokens}]"
        )
