"""Budget Hook — soft/hard budget limits per session, daily, or monthly period."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetConfig:
    """Budget threshold configuration."""

    soft_limit: float
    hard_limit: float
    period: str  # "session" | "daily" | "monthly"


@dataclass(frozen=True)
class BudgetStatus:
    """Result of a budget check."""

    allowed: bool
    warning: bool
    remaining: float


class BudgetExceeded(Exception):
    """Raised when current cost exceeds the hard limit."""


class BudgetHook:
    """Checks spending against a BudgetConfig.

    Parameters
    ----------
    config:
        The budget limits to enforce.
    """

    def __init__(self, config: BudgetConfig) -> None:
        self._config = config

    def check(self, current_cost: float) -> BudgetStatus:
        """Evaluate *current_cost* against configured limits."""
        remaining = max(0.0, self._config.hard_limit - current_cost)
        exceeded = current_cost >= self._config.hard_limit
        warning = (
            not exceeded and current_cost >= self._config.soft_limit
        )
        return BudgetStatus(
            allowed=not exceeded,
            warning=warning,
            remaining=remaining,
        )

    def is_exceeded(self, current_cost: float) -> bool:
        """Return True if *current_cost* meets or exceeds the hard limit."""
        return current_cost >= self._config.hard_limit


__all__ = ["BudgetConfig", "BudgetStatus", "BudgetExceeded", "BudgetHook"]
