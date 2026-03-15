"""Cost budget alerts — Task 429.

Tracks daily and monthly LLM spend and fires alerts when configurable
thresholds are reached.

Usage::

    tracker = BudgetTracker(daily_limit_usd=5.0, monthly_limit_usd=50.0)
    tracker.record_cost(0.03)
    for alert in tracker.check_limits():
        print(alert.level, alert.period, alert.pct)
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Alert threshold percentages
_WARNING_PCT = 80.0
_CRITICAL_PCT = 95.0
_EXCEEDED_PCT = 100.0


class AlertLevel(str, Enum):
    """Severity level for a budget alert."""

    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EXCEEDED = "EXCEEDED"


@dataclass(frozen=True)
class BudgetAlert:
    """Represents a single budget threshold breach.

    Attributes:
        level: Severity of the alert.
        period: ``"daily"`` or ``"monthly"``.
        spent: Actual spend so far for the period.
        limit: The configured limit for the period.
        pct: Percentage of limit consumed (0–100+).
    """

    level: AlertLevel
    period: str
    spent: float
    limit: float
    pct: float

    def __str__(self) -> str:
        return (
            f"[{self.level.value}] {self.period.capitalize()} budget: "
            f"${self.spent:.4f} / ${self.limit:.2f} ({self.pct:.1f}%)"
        )


class BudgetTracker:
    """Accumulates LLM costs and checks against daily/monthly limits.

    Args:
        daily_limit_usd: Maximum USD spend allowed per day.
        monthly_limit_usd: Maximum USD spend allowed per calendar month.
    """

    def __init__(
        self,
        daily_limit_usd: float = 5.0,
        monthly_limit_usd: float = 50.0,
    ) -> None:
        self.daily_limit_usd = daily_limit_usd
        self.monthly_limit_usd = monthly_limit_usd

        # Internal spend accumulators — keyed by ISO date/month strings
        self._daily: dict[str, float] = {}
        self._monthly: dict[str, float] = {}

        # Track fired alerts to avoid repeated notifications in the same period
        self._fired: set[tuple[str, str]] = set()  # (period_key, level)

    # ------------------------------------------------------------------
    # Period key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _today_key() -> str:
        return datetime.date.today().isoformat()

    @staticmethod
    def _month_key() -> str:
        d = datetime.date.today()
        return f"{d.year}-{d.month:02d}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_cost(self, cost_usd: float) -> None:
        """Accumulate *cost_usd* against the current day and month."""
        if cost_usd <= 0:
            return
        day = self._today_key()
        month = self._month_key()
        self._daily[day] = self._daily.get(day, 0.0) + cost_usd
        self._monthly[month] = self._monthly.get(month, 0.0) + cost_usd

    @property
    def daily_spend(self) -> float:
        """Total spend for today."""
        return self._daily.get(self._today_key(), 0.0)

    @property
    def monthly_spend(self) -> float:
        """Total spend for the current month."""
        return self._monthly.get(self._month_key(), 0.0)

    def reset_daily(self) -> None:
        """Clear today's spend counter."""
        self._daily.pop(self._today_key(), None)

    def reset_monthly(self) -> None:
        """Clear this month's spend counter."""
        self._monthly.pop(self._month_key(), None)

    def reset_all(self) -> None:
        """Clear all accumulated spend and fired-alert state."""
        self._daily.clear()
        self._monthly.clear()
        self._fired.clear()

    def check_limits(self) -> list[BudgetAlert]:
        """Return a list of active budget alerts.

        Each (period, level) pair is returned at most once until the period
        resets or :meth:`reset_all` is called.
        """
        alerts: list[BudgetAlert] = []

        day_key = self._today_key()
        month_key = self._month_key()

        checks: list[tuple[str, str, float, float]] = [
            ("daily", day_key, self.daily_spend, self.daily_limit_usd),
            ("monthly", month_key, self.monthly_spend, self.monthly_limit_usd),
        ]

        for period, key, spent, limit in checks:
            if limit <= 0:
                continue
            pct = (spent / limit) * 100.0

            for threshold, level in [
                (_EXCEEDED_PCT, AlertLevel.EXCEEDED),
                (_CRITICAL_PCT, AlertLevel.CRITICAL),
                (_WARNING_PCT, AlertLevel.WARNING),
            ]:
                fire_key = (f"{period}:{key}", level.value)
                if pct >= threshold and fire_key not in self._fired:
                    self._fired.add(fire_key)
                    alerts.append(BudgetAlert(
                        level=level,
                        period=period,
                        spent=spent,
                        limit=limit,
                        pct=pct,
                    ))
                    break  # Only emit the highest applicable level per period

        return alerts

    def status(self) -> dict[str, Any]:
        """Return a dict summarising current spend and limits."""
        return {
            "daily_spend": self.daily_spend,
            "daily_limit": self.daily_limit_usd,
            "daily_pct": (self.daily_spend / self.daily_limit_usd * 100) if self.daily_limit_usd else 0.0,
            "monthly_spend": self.monthly_spend,
            "monthly_limit": self.monthly_limit_usd,
            "monthly_pct": (self.monthly_spend / self.monthly_limit_usd * 100) if self.monthly_limit_usd else 0.0,
        }
