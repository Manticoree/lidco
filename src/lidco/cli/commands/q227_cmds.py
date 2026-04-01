"""Q227 CLI commands: /context-meter, /model-limits, /usage-dashboard, /budget-alerts."""
from __future__ import annotations


def register(registry) -> None:  # noqa: ANN001
    """Register Q227 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /context-meter
    # ------------------------------------------------------------------

    async def context_meter_handler(args: str) -> str:
        from lidco.budget.window_meter import ContextWindowMeter

        parts = args.strip().split()
        limit = int(parts[0]) if parts else 128000
        meter = ContextWindowMeter(context_limit=limit)
        return meter.summary()

    # ------------------------------------------------------------------
    # /model-limits
    # ------------------------------------------------------------------

    async def model_limits_handler(args: str) -> str:
        from lidco.budget.model_registry import ModelRegistry

        reg = ModelRegistry()
        model_name = args.strip()
        if not model_name:
            return reg.summary()
        info = reg.get(model_name)
        if info is None:
            return f"Unknown model: {model_name}"
        return (
            f"{info.name}: context={info.context_window:,}, "
            f"max_output={info.max_output:,}, provider={info.provider}"
        )

    # ------------------------------------------------------------------
    # /usage-dashboard
    # ------------------------------------------------------------------

    async def usage_dashboard_handler(args: str) -> str:
        from lidco.budget.usage_dashboard import UsageDashboard

        dashboard = UsageDashboard()
        return dashboard.summary()

    # ------------------------------------------------------------------
    # /budget-alerts
    # ------------------------------------------------------------------

    async def budget_alerts_handler(args: str) -> str:
        from lidco.budget.threshold_alerter import ThresholdAlerter

        alerter = ThresholdAlerter()
        return alerter.summary()

    registry.register(
        SlashCommand("context-meter", "Show context window utilization", context_meter_handler)
    )
    registry.register(
        SlashCommand("model-limits", "Show model context limits", model_limits_handler)
    )
    registry.register(
        SlashCommand("usage-dashboard", "Show usage dashboard", usage_dashboard_handler)
    )
    registry.register(
        SlashCommand("budget-alerts", "Show budget alert thresholds", budget_alerts_handler)
    )
