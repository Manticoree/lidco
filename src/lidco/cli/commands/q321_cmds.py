"""
Q321 CLI commands — /cloud-cost, /cost-forecast, /find-savings, /cost-dashboard

Registered via register_q321_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q321_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q321 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /cloud-cost — Analyze cloud spending
    # ------------------------------------------------------------------
    async def cloud_cost_handler(args: str) -> str:
        """
        Usage: /cloud-cost [--start YYYY-MM-DD] [--end YYYY-MM-DD]
        """
        from lidco.cloudcost.analyzer import CostAnalyzer

        parts = shlex.split(args) if args.strip() else []
        start: str | None = None
        end: str | None = None

        i = 0
        while i < len(parts):
            if parts[i] == "--start" and i + 1 < len(parts):
                start = parts[i + 1]
                i += 2
            elif parts[i] == "--end" and i + 1 < len(parts):
                end = parts[i + 1]
                i += 2
            else:
                i += 1

        analyzer = CostAnalyzer()
        breakdown = analyzer.analyze(period_start=start, period_end=end)

        lines = [
            f"Cloud Cost: ${breakdown.total_cost:.2f} {breakdown.currency}",
            f"Period: {breakdown.period_start} .. {breakdown.period_end}",
            "",
        ]
        if breakdown.top_services:
            lines.append("Top services:")
            for svc, cost in breakdown.top_services[:10]:
                lines.append(f"  {svc}: ${cost:.2f}")

        if breakdown.unused_resources:
            lines.append("")
            lines.append(f"Unused resources: {len(breakdown.unused_resources)}")
            for u in breakdown.unused_resources[:5]:
                lines.append(f"  {u.resource_id} ({u.service}): ${u.monthly_cost:.2f}/mo — {u.reason}")

        if breakdown.right_sizing:
            lines.append("")
            lines.append(f"Right-sizing suggestions: {len(breakdown.right_sizing)}")
            for r in breakdown.right_sizing[:5]:
                lines.append(
                    f"  {r.resource_id}: {r.current_type} -> {r.suggested_type} "
                    f"(save ${r.savings:.2f}/mo)"
                )

        return "\n".join(lines)

    registry.register_async(
        "cloud-cost",
        "Analyze cloud spending breakdown",
        cloud_cost_handler,
    )

    # ------------------------------------------------------------------
    # /cost-forecast — Predict future costs
    # ------------------------------------------------------------------
    async def cost_forecast_handler(args: str) -> str:
        """
        Usage: /cost-forecast [--budget N] [--periods N]
        """
        from lidco.cloudcost.forecaster import CostForecaster

        parts = shlex.split(args) if args.strip() else []
        budget: float | None = None
        periods = 3

        i = 0
        while i < len(parts):
            if parts[i] == "--budget" and i + 1 < len(parts):
                try:
                    budget = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--periods" and i + 1 < len(parts):
                try:
                    periods = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        forecaster = CostForecaster(budget=budget)
        result = forecaster.forecast(periods=periods)

        lines = [
            f"Cost Forecast:",
            f"  Current: ${result.current_monthly:.2f}",
            f"  Projected: ${result.projected_monthly:.2f}",
            f"  Trend: {result.trend_direction} ({result.trend_pct:+.1f}%)",
        ]

        if result.forecast_points:
            lines.append("")
            lines.append("Forecast:")
            for pt in result.forecast_points:
                lines.append(f"  {pt.date}: ${pt.amount:.2f}")

        if result.alerts:
            lines.append("")
            for alert in result.alerts:
                lines.append(f"  [{alert.severity.upper()}] {alert.message}")

        return "\n".join(lines)

    registry.register_async(
        "cost-forecast",
        "Predict future cloud costs",
        cost_forecast_handler,
    )

    # ------------------------------------------------------------------
    # /find-savings — Find cost savings opportunities
    # ------------------------------------------------------------------
    async def find_savings_handler(args: str) -> str:
        """
        Usage: /find-savings
        """
        from lidco.cloudcost.savings import SavingsFinder

        finder = SavingsFinder()
        report = finder.find()

        if not report.opportunities:
            return "No savings opportunities found. Add resource data first."

        lines = [
            f"Savings Report:",
            f"  Current annual: ${report.total_current_annual:,.2f}",
            f"  Projected annual: ${report.total_projected_annual:,.2f}",
            f"  Total savings: ${report.total_annual_savings:,.2f}",
            "",
        ]

        for cat, amt in sorted(report.summary_by_category.items()):
            lines.append(f"  {cat}: ${amt:,.2f}")

        lines.append("")
        for opp in report.opportunities[:10]:
            lines.append(
                f"  [{opp.risk}] {opp.description} — save ${opp.annual_savings:,.2f}/yr "
                f"(ROI {opp.roi_pct:.0f}%)"
            )

        return "\n".join(lines)

    registry.register_async(
        "find-savings",
        "Find cloud cost savings opportunities",
        find_savings_handler,
    )

    # ------------------------------------------------------------------
    # /cost-dashboard — Cost visualization dashboard
    # ------------------------------------------------------------------
    async def cost_dashboard_handler(args: str) -> str:
        """
        Usage: /cost-dashboard [--threshold N]
        """
        from lidco.cloudcost.dashboard import CostDashboard

        parts = shlex.split(args) if args.strip() else []
        threshold = 2.0

        i = 0
        while i < len(parts):
            if parts[i] == "--threshold" and i + 1 < len(parts):
                try:
                    threshold = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        dashboard = CostDashboard(anomaly_threshold=threshold)
        report = dashboard.build()

        lines = [
            f"Cost Dashboard: ${report.total_cost:.2f} {report.currency}",
            "",
        ]

        if report.monthly_trend:
            lines.append("Monthly trend:")
            for pt in report.monthly_trend:
                lines.append(f"  {pt.label}: ${pt.amount:.2f}")

        if report.environments:
            lines.append("")
            lines.append("By environment:")
            for env in report.environments:
                lines.append(f"  {env.environment}: ${env.total_cost:.2f}")

        if report.anomalies:
            lines.append("")
            lines.append("Anomalies:")
            for a in report.anomalies:
                lines.append(
                    f"  [{a.severity}] {a.date}: ${a.amount:.2f} "
                    f"(expected ${a.expected:.2f}, {a.deviation_pct:+.1f}%)"
                )

        return "\n".join(lines)

    registry.register_async(
        "cost-dashboard",
        "Cost visualization dashboard",
        cost_dashboard_handler,
    )
