"""
Cost Dashboard — Cost visualization with daily/weekly/monthly trends,
per-environment breakdown, tag grouping, and anomaly highlighting.

Pure stdlib.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class TrendPoint:
    """Single data point in a trend series."""

    label: str
    amount: float


@dataclass(frozen=True)
class Anomaly:
    """A cost anomaly (spike or drop)."""

    date: str
    amount: float
    expected: float
    deviation_pct: float
    severity: str  # "info" | "warning" | "critical"


@dataclass(frozen=True)
class EnvironmentCost:
    """Costs for one environment (prod, staging, dev, etc.)."""

    environment: str
    total_cost: float
    service_breakdown: dict[str, float]


@dataclass(frozen=True)
class TagGroup:
    """Costs grouped by a tag key-value pair."""

    tag_key: str
    tag_value: str
    total_cost: float


@dataclass(frozen=True)
class DashboardReport:
    """Full dashboard data."""

    total_cost: float
    currency: str
    daily_trend: list[TrendPoint]
    weekly_trend: list[TrendPoint]
    monthly_trend: list[TrendPoint]
    environments: list[EnvironmentCost]
    tag_groups: list[TagGroup]
    anomalies: list[Anomaly]


class CostDashboard:
    """Build a cost dashboard from raw cost records."""

    def __init__(self, currency: str = "USD", anomaly_threshold: float = 2.0) -> None:
        self._currency = currency
        self._anomaly_threshold = anomaly_threshold
        self._records: list[dict[str, Any]] = []

    def add_records(self, records: Sequence[dict[str, Any]]) -> None:
        """Add raw cost records.

        Each record: ``date`` (YYYY-MM-DD), ``amount``, ``service``,
        ``environment``, ``tags`` (dict).
        """
        self._records = [*self._records, *records]

    def build(self) -> DashboardReport:
        """Produce the full dashboard report."""
        daily = self._aggregate_by("date")
        weekly = self._aggregate_weekly()
        monthly = self._aggregate_monthly()

        envs = self._aggregate_environments()
        tags = self._aggregate_tags()
        anomalies = self._detect_anomalies(daily)

        total = round(sum(t.amount for t in daily), 2)

        return DashboardReport(
            total_cost=total,
            currency=self._currency,
            daily_trend=daily,
            weekly_trend=weekly,
            monthly_trend=monthly,
            environments=envs,
            tag_groups=tags,
            anomalies=anomalies,
        )

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------

    def _aggregate_by(self, key: str) -> list[TrendPoint]:
        buckets: dict[str, float] = {}
        for rec in self._records:
            label = rec.get(key, "unknown")
            buckets[label] = buckets.get(label, 0) + float(rec.get("amount", 0))
        return [
            TrendPoint(label=k, amount=round(v, 2))
            for k, v in sorted(buckets.items())
        ]

    def _aggregate_weekly(self) -> list[TrendPoint]:
        buckets: dict[str, float] = {}
        for rec in self._records:
            d = rec.get("date", "")
            week = d[:8] + "W" if len(d) >= 8 else d  # rough week bucket
            buckets[week] = buckets.get(week, 0) + float(rec.get("amount", 0))
        return [
            TrendPoint(label=k, amount=round(v, 2))
            for k, v in sorted(buckets.items())
        ]

    def _aggregate_monthly(self) -> list[TrendPoint]:
        buckets: dict[str, float] = {}
        for rec in self._records:
            d = rec.get("date", "")
            month = d[:7] if len(d) >= 7 else d
            buckets[month] = buckets.get(month, 0) + float(rec.get("amount", 0))
        return [
            TrendPoint(label=k, amount=round(v, 2))
            for k, v in sorted(buckets.items())
        ]

    def _aggregate_environments(self) -> list[EnvironmentCost]:
        env_map: dict[str, dict[str, float]] = {}
        for rec in self._records:
            env = rec.get("environment", "default")
            svc = rec.get("service", "unknown")
            amt = float(rec.get("amount", 0))
            if env not in env_map:
                env_map[env] = {}
            env_map[env][svc] = env_map[env].get(svc, 0) + amt
        result: list[EnvironmentCost] = []
        for env_name, svcs in sorted(env_map.items()):
            total = round(sum(svcs.values()), 2)
            rounded = {k: round(v, 2) for k, v in svcs.items()}
            result.append(
                EnvironmentCost(
                    environment=env_name,
                    total_cost=total,
                    service_breakdown=rounded,
                )
            )
        return result

    def _aggregate_tags(self) -> list[TagGroup]:
        tag_map: dict[tuple[str, str], float] = {}
        for rec in self._records:
            tags = rec.get("tags", {})
            amt = float(rec.get("amount", 0))
            for k, v in tags.items():
                key = (k, v)
                tag_map[key] = tag_map.get(key, 0) + amt
        return [
            TagGroup(tag_key=k, tag_value=v, total_cost=round(amt, 2))
            for (k, v), amt in sorted(tag_map.items())
        ]

    def _detect_anomalies(self, daily: list[TrendPoint]) -> list[Anomaly]:
        if len(daily) < 3:
            return []
        amounts = [p.amount for p in daily]
        mean = statistics.mean(amounts)
        stdev = statistics.stdev(amounts) if len(amounts) >= 2 else 0.0
        if stdev < 0.01:
            return []
        anomalies: list[Anomaly] = []
        for pt in daily:
            z = abs(pt.amount - mean) / stdev
            if z >= self._anomaly_threshold:
                dev_pct = round((pt.amount - mean) / mean * 100, 2) if mean else 0.0
                if z >= 3.0:
                    severity = "critical"
                elif z >= self._anomaly_threshold:
                    severity = "warning"
                else:
                    severity = "info"
                anomalies.append(
                    Anomaly(
                        date=pt.label,
                        amount=pt.amount,
                        expected=round(mean, 2),
                        deviation_pct=dev_pct,
                        severity=severity,
                    )
                )
        return anomalies
