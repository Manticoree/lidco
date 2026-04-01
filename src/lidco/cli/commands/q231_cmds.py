"""Q231 CLI commands: /budget-status, /budget-report, /budget-config, /budget-reset."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q231 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /budget-status
    # ------------------------------------------------------------------

    async def budget_status_handler(args: str) -> str:
        from lidco.budget.controller import BudgetController

        ctrl = BudgetController()
        # Simulate a few turns for demo
        ctrl.process_turn("user", 5000)
        ctrl.process_turn("assistant", 8000)
        return ctrl.summary()

    # ------------------------------------------------------------------
    # /budget-report
    # ------------------------------------------------------------------

    async def budget_report_handler(args: str) -> str:
        from lidco.budget.reporter import BudgetReporter

        reporter = BudgetReporter()
        limit = 128_000
        used = 50_000
        parts = args.strip().split()
        if len(parts) >= 1:
            try:
                used = int(parts[0])
            except ValueError:
                pass
        remaining = max(0, limit - used)
        report = reporter.create_report(
            total=used, remaining=remaining, limit=limit,
            compactions=0, saved=0, peak=used, turns=1,
        )
        return reporter.format_report(report)

    # ------------------------------------------------------------------
    # /budget-config
    # ------------------------------------------------------------------

    async def budget_config_handler(args: str) -> str:
        from lidco.budget.config import BudgetConfigManager

        mgr = BudgetConfigManager()
        parts = args.strip().split()
        if len(parts) >= 2:
            model = parts[0]
            try:
                limit = int(parts[1])
            except ValueError:
                return mgr.summary()
            from lidco.budget.config import BudgetConfig
            mgr.set_override(model, BudgetConfig(context_limit=limit))
        return mgr.summary()

    # ------------------------------------------------------------------
    # /budget-reset
    # ------------------------------------------------------------------

    async def budget_reset_handler(args: str) -> str:
        from lidco.budget.controller import BudgetController

        ctrl = BudgetController()
        ctrl.process_turn("user", 10000)
        ctrl.reset()
        return f"Budget reset. Remaining: {ctrl.remaining():,}"

    registry.register(SlashCommand("budget-status", "Show unified budget status", budget_status_handler))
    registry.register(SlashCommand("budget-report", "Generate budget report", budget_report_handler))
    registry.register(SlashCommand("budget-config", "View/set budget config", budget_config_handler))
    registry.register(SlashCommand("budget-reset", "Reset budget controller", budget_reset_handler))
