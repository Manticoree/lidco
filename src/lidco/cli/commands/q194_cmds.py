"""Q194 CLI commands: /cost-track, /cost-dashboard, /budget-hook, /cost-project."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q194 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    _state: dict[str, object] = {}

    # ------------------------------------------------------------------
    # /cost-track
    # ------------------------------------------------------------------

    async def cost_track_handler(args: str) -> str:
        from lidco.economics.cost_hook import CostHook, ModelPricing

        hook: CostHook | None = _state.get("cost_hook")  # type: ignore[assignment]
        if hook is None:
            hook = CostHook(
                pricing=(
                    ModelPricing("gpt-4", 0.03, 0.06),
                    ModelPricing("gpt-3.5-turbo", 0.0015, 0.002),
                )
            )
            _state["cost_hook"] = hook

        parts = args.strip().split()
        if not parts:
            return f"Total cost: ${hook.total_cost:.6f} ({len(hook.records)} records)"

        if parts[0] == "record" and len(parts) >= 4:
            model = parts[1]
            inp = int(parts[2])
            out = int(parts[3])
            rec = hook.record(model, inp, out)
            return f"Recorded: {rec.model} ${rec.cost:.6f}"

        if parts[0] == "by-model":
            by_m = hook.by_model()
            if not by_m:
                return "No records."
            lines = [f"  {m}: ${c:.6f}" for m, c in by_m.items()]
            return "Cost by model:\n" + "\n".join(lines)

        return "Usage: /cost-track [record <model> <in> <out>|by-model]"

    # ------------------------------------------------------------------
    # /cost-dashboard
    # ------------------------------------------------------------------

    async def cost_dashboard_handler(args: str) -> str:
        from lidco.economics.cost_dashboard import CostDashboard
        from lidco.economics.cost_hook import CostHook

        hook: CostHook | None = _state.get("cost_hook")  # type: ignore[assignment]
        if hook is None:
            return "No cost data. Use /cost-track record first."
        dashboard = CostDashboard(hook.records)
        return dashboard.format_report()

    # ------------------------------------------------------------------
    # /budget-hook
    # ------------------------------------------------------------------

    async def budget_hook_handler(args: str) -> str:
        from lidco.economics.budget_hook import BudgetConfig, BudgetHook
        from lidco.economics.cost_hook import CostHook

        parts = args.strip().split()
        if not parts:
            return "Usage: /budget-hook set <soft> <hard> <period>|check"

        if parts[0] == "set" and len(parts) >= 4:
            soft = float(parts[1])
            hard = float(parts[2])
            period = parts[3]
            config = BudgetConfig(soft_limit=soft, hard_limit=hard, period=period)
            hook = BudgetHook(config)
            _state["budget_hook"] = hook
            return f"Budget set: soft=${soft}, hard=${hard}, period={period}"

        if parts[0] == "check":
            bh: BudgetHook | None = _state.get("budget_hook")  # type: ignore[assignment]
            if bh is None:
                return "No budget configured. Use /budget-hook set first."
            ch: CostHook | None = _state.get("cost_hook")  # type: ignore[assignment]
            current = ch.total_cost if ch else 0.0
            status = bh.check(current)
            return (
                f"Allowed: {status.allowed} | Warning: {status.warning} | "
                f"Remaining: ${status.remaining:.6f}"
            )

        return "Usage: /budget-hook set <soft> <hard> <period>|check"

    # ------------------------------------------------------------------
    # /cost-project
    # ------------------------------------------------------------------

    async def cost_project_handler(args: str) -> str:
        from lidco.economics.cost_hook import CostHook
        from lidco.economics.cost_projector import CostProjector

        hook: CostHook | None = _state.get("cost_hook")  # type: ignore[assignment]
        if hook is None:
            return "No cost data. Use /cost-track record first."

        projector = CostProjector(hook.records)
        parts = args.strip().split()
        remaining = int(parts[0]) if parts else 10
        proj = projector.project(remaining)
        trend = projector.trend()
        return (
            f"Projected total: ${proj.estimated_total:.6f} | "
            f"Remaining: ${proj.remaining:.6f} | "
            f"Confidence: {proj.confidence:.2f} | Trend: {trend}"
        )

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------

    registry.register(SlashCommand("cost-track", "Track per-call LLM costs", cost_track_handler))
    registry.register(SlashCommand("cost-dashboard", "Show cost breakdown dashboard", cost_dashboard_handler))
    registry.register(SlashCommand("budget-hook", "Configure and check budget limits", budget_hook_handler))
    registry.register(SlashCommand("cost-project", "Project future costs and trends", cost_project_handler))
