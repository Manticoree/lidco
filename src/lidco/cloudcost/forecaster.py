"""
Cost Forecaster — Predict future cloud costs via trend extrapolation,
seasonal pattern detection, and budget alerts.

Pure stdlib.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class CostDataPoint:
    """Single cost data point (date string + amount)."""

    date: str
    amount: float


@dataclass(frozen=True)
class BudgetAlert:
    """Alert when projected costs exceed a budget."""

    budget: float
    projected: float
    overage: float
    severity: str  # "warning" | "critical"
    message: str


@dataclass(frozen=True)
class SeasonalPattern:
    """Detected seasonal cost pattern."""

    period: str  # e.g. "weekly", "monthly"
    peak_index: int
    trough_index: int
    amplitude: float


@dataclass(frozen=True)
class CostForecast:
    """Forecast result."""

    current_monthly: float
    projected_monthly: float
    trend_direction: str  # "up" | "down" | "stable"
    trend_pct: float
    forecast_points: list[CostDataPoint]
    alerts: list[BudgetAlert]
    seasonal: SeasonalPattern | None


class CostForecaster:
    """Predict future cloud costs from historical data."""

    def __init__(self, budget: float | None = None) -> None:
        self._budget = budget
        self._data: list[CostDataPoint] = []

    def add_data(self, points: Sequence[CostDataPoint]) -> None:
        """Add historical cost data points."""
        self._data = [*self._data, *points]

    def forecast(self, periods: int = 3) -> CostForecast:
        """Generate a cost forecast for *periods* future intervals.

        Uses simple linear regression for trend extrapolation and basic
        seasonal detection.
        """
        if not self._data:
            return CostForecast(
                current_monthly=0.0,
                projected_monthly=0.0,
                trend_direction="stable",
                trend_pct=0.0,
                forecast_points=[],
                alerts=[],
                seasonal=None,
            )

        amounts = [p.amount for p in self._data]
        n = len(amounts)

        # Simple linear regression  y = a + b*x
        slope, intercept = self._linear_regression(amounts)

        current = amounts[-1]
        projected_vals: list[float] = []
        for i in range(1, periods + 1):
            projected_vals.append(round(intercept + slope * (n - 1 + i), 2))

        projected = projected_vals[-1] if projected_vals else current

        # Trend
        if n >= 2:
            pct = ((projected - current) / current * 100) if current else 0.0
        else:
            pct = 0.0
        pct = round(pct, 2)

        if pct > 5:
            direction = "up"
        elif pct < -5:
            direction = "down"
        else:
            direction = "stable"

        # Build forecast points
        forecast_pts: list[CostDataPoint] = []
        for i, val in enumerate(projected_vals, start=1):
            forecast_pts.append(CostDataPoint(date=f"T+{i}", amount=val))

        # Budget alerts
        alerts = self._check_budget(projected)

        # Seasonal
        seasonal = self._detect_seasonal(amounts)

        return CostForecast(
            current_monthly=round(current, 2),
            projected_monthly=round(projected, 2),
            trend_direction=direction,
            trend_pct=pct,
            forecast_points=forecast_pts,
            alerts=alerts,
            seasonal=seasonal,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _linear_regression(values: list[float]) -> tuple[float, float]:
        """Return (slope, intercept) for values indexed 0..n-1."""
        n = len(values)
        if n < 2:
            return 0.0, values[0] if values else 0.0
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        if den == 0:
            return 0.0, y_mean
        slope = num / den
        intercept = y_mean - slope * x_mean
        return round(slope, 4), round(intercept, 4)

    def _check_budget(self, projected: float) -> list[BudgetAlert]:
        if self._budget is None:
            return []
        alerts: list[BudgetAlert] = []
        if projected > self._budget:
            overage = round(projected - self._budget, 2)
            severity = "critical" if overage > self._budget * 0.2 else "warning"
            alerts.append(
                BudgetAlert(
                    budget=self._budget,
                    projected=round(projected, 2),
                    overage=overage,
                    severity=severity,
                    message=f"Projected cost ${projected:.2f} exceeds budget ${self._budget:.2f} by ${overage:.2f}",
                )
            )
        return alerts

    @staticmethod
    def _detect_seasonal(values: list[float]) -> SeasonalPattern | None:
        """Very basic seasonal detection — needs at least 6 data points."""
        if len(values) < 6:
            return None
        peak_idx = 0
        trough_idx = 0
        for i, v in enumerate(values):
            if v > values[peak_idx]:
                peak_idx = i
            if v < values[trough_idx]:
                trough_idx = i
        amplitude = round(values[peak_idx] - values[trough_idx], 2)
        if amplitude < 0.01:
            return None
        period = "monthly" if len(values) >= 12 else "weekly"
        return SeasonalPattern(
            period=period,
            peak_index=peak_idx,
            trough_index=trough_idx,
            amplitude=amplitude,
        )
