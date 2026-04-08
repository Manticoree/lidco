"""
Savings Finder — Identify cost savings opportunities including reserved
instances, spot instances, auto-scaling, and ROI calculation.

Pure stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class SavingsOpportunity:
    """A single savings opportunity."""

    category: str  # "reserved" | "spot" | "auto-scaling" | "cleanup" | "rightsizing"
    description: str
    current_cost: float
    projected_cost: float
    annual_savings: float
    roi_pct: float
    risk: str  # "low" | "medium" | "high"
    resource_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SavingsReport:
    """Full savings report."""

    total_current_annual: float
    total_projected_annual: float
    total_annual_savings: float
    opportunities: list[SavingsOpportunity]
    summary_by_category: dict[str, float]


class SavingsFinder:
    """Find cloud cost savings opportunities from resource and usage data."""

    def __init__(self) -> None:
        self._resources: list[dict[str, Any]] = []
        self._usage: list[dict[str, Any]] = []

    def add_resources(self, resources: Sequence[dict[str, Any]]) -> None:
        """Add resource data.

        Each dict: ``resource_id``, ``service``, ``type``, ``monthly_cost``,
        ``cpu_util``, ``on_demand`` (bool), ``scalable`` (bool).
        """
        self._resources = [*self._resources, *resources]

    def add_usage_patterns(self, patterns: Sequence[dict[str, Any]]) -> None:
        """Add usage pattern data.

        Each dict: ``resource_id``, ``peak_hours``, ``off_hours_util``,
        ``interruptible`` (bool).
        """
        self._usage = [*self._usage, *patterns]

    def find(self) -> SavingsReport:
        """Analyse resources and return savings opportunities."""
        opportunities: list[SavingsOpportunity] = []

        usage_map = {u["resource_id"]: u for u in self._usage}

        for res in self._resources:
            rid = res.get("resource_id", "")
            monthly = float(res.get("monthly_cost", 0))
            annual = monthly * 12

            # Reserved instance opportunity
            if res.get("on_demand", False):
                reserved_annual = annual * 0.6  # ~40% savings
                opportunities.append(
                    SavingsOpportunity(
                        category="reserved",
                        description=f"Convert {rid} to 1-year reserved instance",
                        current_cost=annual,
                        projected_cost=round(reserved_annual, 2),
                        annual_savings=round(annual - reserved_annual, 2),
                        roi_pct=40.0,
                        risk="low",
                        resource_ids=[rid],
                    )
                )

            # Spot instance opportunity
            usage = usage_map.get(rid, {})
            if usage.get("interruptible", False):
                spot_annual = annual * 0.3  # ~70% savings
                opportunities.append(
                    SavingsOpportunity(
                        category="spot",
                        description=f"Move {rid} to spot instances",
                        current_cost=annual,
                        projected_cost=round(spot_annual, 2),
                        annual_savings=round(annual - spot_annual, 2),
                        roi_pct=70.0,
                        risk="high",
                        resource_ids=[rid],
                    )
                )

            # Auto-scaling opportunity
            if res.get("scalable", False) and usage.get("off_hours_util", 100) < 20:
                scaled_annual = annual * 0.65
                opportunities.append(
                    SavingsOpportunity(
                        category="auto-scaling",
                        description=f"Enable auto-scaling for {rid} (low off-hours util)",
                        current_cost=annual,
                        projected_cost=round(scaled_annual, 2),
                        annual_savings=round(annual - scaled_annual, 2),
                        roi_pct=35.0,
                        risk="medium",
                        resource_ids=[rid],
                    )
                )

            # Right-sizing
            cpu = float(res.get("cpu_util", 100))
            if cpu < 20:
                sized_annual = annual * 0.5
                opportunities.append(
                    SavingsOpportunity(
                        category="rightsizing",
                        description=f"Downsize {rid} (CPU util {cpu:.0f}%)",
                        current_cost=annual,
                        projected_cost=round(sized_annual, 2),
                        annual_savings=round(annual - sized_annual, 2),
                        roi_pct=50.0,
                        risk="low",
                        resource_ids=[rid],
                    )
                )

        total_current = round(sum(o.current_cost for o in opportunities), 2)
        total_projected = round(sum(o.projected_cost for o in opportunities), 2)
        total_savings = round(sum(o.annual_savings for o in opportunities), 2)

        cat_summary: dict[str, float] = {}
        for o in opportunities:
            cat_summary[o.category] = round(
                cat_summary.get(o.category, 0) + o.annual_savings, 2
            )

        return SavingsReport(
            total_current_annual=total_current,
            total_projected_annual=total_projected,
            total_annual_savings=total_savings,
            opportunities=opportunities,
            summary_by_category=cat_summary,
        )
