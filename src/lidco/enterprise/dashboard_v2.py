"""Enterprise dashboard with org-wide metrics and ROI calculation."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.enterprise.aggregator import UsageAggregator
from lidco.enterprise.fleet import FleetManager


@dataclass(frozen=True)
class OrgMetrics:
    """Organization-wide metrics snapshot."""

    total_instances: int
    healthy_instances: int
    total_users: int
    total_tokens: int
    total_cost: float
    adoption_rate: float
    roi_estimate: float


class EnterpriseDashboard:
    """Org-wide dashboard combining fleet and usage data."""

    def __init__(self, fleet: FleetManager, aggregator: UsageAggregator) -> None:
        self._fleet = fleet
        self._aggregator = aggregator

    def adoption_rate(self) -> float:
        """Ratio of healthy instances to total."""
        all_inst = self._fleet.all_instances()
        if not all_inst:
            return 0.0
        healthy = len(self._fleet.by_status("healthy"))
        return healthy / len(all_inst)

    def roi_estimate(
        self,
        developer_hourly_rate: float = 75.0,
        hours_saved_per_1k_tokens: float = 0.1,
    ) -> float:
        """Estimate ROI based on token usage and developer cost savings."""
        totals = self._aggregator.total()
        tokens = totals["tokens"]
        cost = totals["cost"]
        hours_saved = (tokens / 1000.0) * hours_saved_per_1k_tokens
        value_generated = hours_saved * developer_hourly_rate
        if cost <= 0:
            return value_generated
        return value_generated - cost

    def metrics(self) -> OrgMetrics:
        """Compute comprehensive org metrics."""
        all_inst = self._fleet.all_instances()
        healthy = len(self._fleet.by_status("healthy"))
        totals = self._aggregator.total()
        teams = self._aggregator.by_team()
        return OrgMetrics(
            total_instances=len(all_inst),
            healthy_instances=healthy,
            total_users=len(teams),
            total_tokens=totals["tokens"],
            total_cost=totals["cost"],
            adoption_rate=self.adoption_rate(),
            roi_estimate=self.roi_estimate(),
        )

    def executive_summary(self) -> str:
        """Plain text executive summary."""
        m = self.metrics()
        return (
            f"Fleet: {m.total_instances} instances ({m.healthy_instances} healthy). "
            f"Users: {m.total_users}. "
            f"Tokens: {m.total_tokens}. "
            f"Cost: ${m.total_cost:.2f}. "
            f"Adoption: {m.adoption_rate:.0%}. "
            f"ROI: ${m.roi_estimate:.2f}."
        )

    def render_text(self) -> str:
        """Formatted dashboard text."""
        m = self.metrics()
        lines = [
            "=== Enterprise Dashboard ===",
            f"Instances:  {m.total_instances} total, {m.healthy_instances} healthy",
            f"Users:      {m.total_users}",
            f"Tokens:     {m.total_tokens}",
            f"Cost:       ${m.total_cost:.2f}",
            f"Adoption:   {m.adoption_rate:.0%}",
            f"ROI:        ${m.roi_estimate:.2f}",
            "============================",
        ]
        return "\n".join(lines)

    def summary(self) -> dict:
        """Return summary dict."""
        m = self.metrics()
        return {
            "total_instances": m.total_instances,
            "healthy_instances": m.healthy_instances,
            "total_users": m.total_users,
            "total_tokens": m.total_tokens,
            "total_cost": m.total_cost,
            "adoption_rate": m.adoption_rate,
            "roi_estimate": m.roi_estimate,
        }
