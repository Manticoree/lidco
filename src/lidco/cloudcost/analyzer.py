"""
Cost Analyzer — Analyze cloud spending with per-service breakdown,
unused resource detection, and right-sizing suggestions.

Pure stdlib.  No cloud SDK dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Sequence


@dataclass(frozen=True)
class ServiceCost:
    """Cost entry for one cloud service."""

    service: str
    cost: float
    currency: str = "USD"
    usage_hours: float = 0.0
    region: str = ""
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class UnusedResource:
    """A resource identified as unused or underutilized."""

    resource_id: str
    service: str
    monthly_cost: float
    reason: str
    last_active: str = ""


@dataclass(frozen=True)
class RightSizingSuggestion:
    """Suggestion to resize a resource for cost savings."""

    resource_id: str
    service: str
    current_type: str
    suggested_type: str
    current_cost: float
    projected_cost: float

    @property
    def savings(self) -> float:
        return round(self.current_cost - self.projected_cost, 2)


@dataclass(frozen=True)
class CostBreakdown:
    """Full cost analysis result."""

    total_cost: float
    currency: str
    period_start: str
    period_end: str
    services: list[ServiceCost]
    unused_resources: list[UnusedResource]
    right_sizing: list[RightSizingSuggestion]
    top_services: list[tuple[str, float]]


class CostAnalyzer:
    """Analyze cloud spending from cost records.

    Accepts raw cost records (list of dicts) and produces a breakdown
    with per-service totals, unused resource detection, and right-sizing
    suggestions.
    """

    def __init__(self, currency: str = "USD") -> None:
        self._currency = currency
        self._records: list[dict[str, Any]] = []
        self._resources: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def add_cost_records(self, records: Sequence[dict[str, Any]]) -> None:
        """Add raw cost records.

        Each record should have at least ``service`` and ``cost`` keys.
        Optional: ``usage_hours``, ``region``, ``tags``, ``date``.
        """
        self._records = [*self._records, *records]

    def add_resources(self, resources: Sequence[dict[str, Any]]) -> None:
        """Add resource utilization data for unused / right-sizing analysis.

        Each resource dict should have: ``resource_id``, ``service``,
        ``monthly_cost``, ``cpu_util``, ``last_active``, ``type``.
        """
        self._resources = [*self._resources, *resources]

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def analyze(
        self,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> CostBreakdown:
        """Produce a full cost breakdown."""
        filtered = self._filter_by_period(period_start, period_end)

        service_totals: dict[str, float] = {}
        service_costs: list[ServiceCost] = []

        for rec in filtered:
            svc = rec.get("service", "unknown")
            cost = float(rec.get("cost", 0))
            service_totals[svc] = service_totals.get(svc, 0.0) + cost
            service_costs.append(
                ServiceCost(
                    service=svc,
                    cost=cost,
                    currency=self._currency,
                    usage_hours=float(rec.get("usage_hours", 0)),
                    region=rec.get("region", ""),
                    tags=dict(rec.get("tags", {})),
                )
            )

        total = round(sum(service_totals.values()), 2)
        top = sorted(service_totals.items(), key=lambda t: t[1], reverse=True)

        unused = self._find_unused()
        rightsizing = self._find_right_sizing()

        p_start = period_start or (filtered[0].get("date", "") if filtered else "")
        p_end = period_end or (filtered[-1].get("date", "") if filtered else "")

        return CostBreakdown(
            total_cost=total,
            currency=self._currency,
            period_start=p_start,
            period_end=p_end,
            services=service_costs,
            unused_resources=unused,
            right_sizing=rightsizing,
            top_services=top,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _filter_by_period(
        self, start: str | None, end: str | None
    ) -> list[dict[str, Any]]:
        if not start and not end:
            return list(self._records)
        result: list[dict[str, Any]] = []
        for rec in self._records:
            d = rec.get("date", "")
            if start and d < start:
                continue
            if end and d > end:
                continue
            result.append(rec)
        return result

    def _find_unused(self) -> list[UnusedResource]:
        unused: list[UnusedResource] = []
        for res in self._resources:
            cpu = float(res.get("cpu_util", 100))
            last = res.get("last_active", "")
            if cpu < 1.0:
                unused.append(
                    UnusedResource(
                        resource_id=res.get("resource_id", ""),
                        service=res.get("service", ""),
                        monthly_cost=float(res.get("monthly_cost", 0)),
                        reason="CPU utilization < 1%",
                        last_active=last,
                    )
                )
            elif last:
                try:
                    last_dt = datetime.fromisoformat(last)
                    if datetime.now() - last_dt > timedelta(days=30):
                        unused.append(
                            UnusedResource(
                                resource_id=res.get("resource_id", ""),
                                service=res.get("service", ""),
                                monthly_cost=float(res.get("monthly_cost", 0)),
                                reason="Inactive for 30+ days",
                                last_active=last,
                            )
                        )
                except (ValueError, TypeError):
                    pass
        return unused

    def _find_right_sizing(self) -> list[RightSizingSuggestion]:
        suggestions: list[RightSizingSuggestion] = []
        size_ladder = {
            "xlarge": ("large", 0.5),
            "large": ("medium", 0.5),
            "medium": ("small", 0.5),
            "2xlarge": ("xlarge", 0.5),
            "4xlarge": ("2xlarge", 0.5),
        }
        for res in self._resources:
            cpu = float(res.get("cpu_util", 100))
            rtype = res.get("type", "")
            if cpu < 30.0 and rtype in size_ladder:
                suggested, ratio = size_ladder[rtype]
                current_cost = float(res.get("monthly_cost", 0))
                suggestions.append(
                    RightSizingSuggestion(
                        resource_id=res.get("resource_id", ""),
                        service=res.get("service", ""),
                        current_type=rtype,
                        suggested_type=suggested,
                        current_cost=current_cost,
                        projected_cost=round(current_cost * ratio, 2),
                    )
                )
        return suggestions
