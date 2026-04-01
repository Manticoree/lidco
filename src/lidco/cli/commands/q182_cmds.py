"""Q182 CLI commands: /budget, /cost-alerts, /model-optimizer, /batch-stats."""
from __future__ import annotations


_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q182 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /budget
    # ------------------------------------------------------------------

    async def budget_handler(args: str) -> str:
        from lidco.economics.budget_enforcer import BudgetEnforcer

        if "budget_enforcer" not in _state:
            _state["budget_enforcer"] = BudgetEnforcer()
        enforcer: BudgetEnforcer = _state["budget_enforcer"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "list":
            budgets = enforcer.list_budgets()
            if not budgets:
                return "No budgets configured."
            lines = [f"{len(budgets)} budget(s):"]
            for usage in budgets:
                pct = usage.fraction * 100
                status = "EXCEEDED" if usage.is_exceeded else ("WARNING" if usage.is_warning else "OK")
                lines.append(
                    f"  {usage.budget.name}: ${usage.spent_dollars:.4f} / "
                    f"${usage.budget.limit_dollars:.2f} ({pct:.1f}%) [{status}]"
                )
            return "\n".join(lines)

        return enforcer.summary()

    # ------------------------------------------------------------------
    # /cost-alerts
    # ------------------------------------------------------------------

    async def cost_alerts_handler(args: str) -> str:
        from lidco.economics.cost_alerts import CostAlertEngine

        if "cost_alert_engine" not in _state:
            _state["cost_alert_engine"] = CostAlertEngine()
        engine: CostAlertEngine = _state["cost_alert_engine"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "rules":
            rules = engine.list_rules()
            if not rules:
                return "No alert rules configured."
            lines = [f"{len(rules)} alert rule(s):"]
            for rule in rules:
                lines.append(f"  {rule.name}: {rule.alert_type} threshold={rule.threshold}")
            return "\n".join(lines)

        if sub == "history":
            alerts = engine.fired_alerts
            if not alerts:
                return "No alerts fired."
            lines = [f"{len(alerts)} alert(s) fired:"]
            for alert in alerts:
                lines.append(f"  [{alert.alert_type}] {alert.rule_name}: {alert.message}")
            return "\n".join(lines)

        return engine.summary()

    # ------------------------------------------------------------------
    # /model-optimizer
    # ------------------------------------------------------------------

    async def model_optimizer_handler(args: str) -> str:
        from lidco.economics.model_optimizer import ModelOptimizer

        if "model_optimizer" not in _state:
            _state["model_optimizer"] = ModelOptimizer()
        optimizer: ModelOptimizer = _state["model_optimizer"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "classify" and rest:
            classification = optimizer.classify_task(rest)
            return (
                f"Task: {rest}\n"
                f"Complexity: {classification.complexity}\n"
                f"Confidence: {classification.confidence:.2f}\n"
                f"Reason: {classification.reason}"
            )

        if sub == "tiers":
            tiers = optimizer.list_tiers()
            if not tiers:
                return "No model tiers configured."
            lines = [f"{len(tiers)} tier(s):"]
            for tier in tiers:
                lines.append(
                    f"  {tier.name}: ${tier.cost_per_1k_input}/1k in, "
                    f"quality={tier.quality_score:.2f}"
                )
            return "\n".join(lines)

        return optimizer.summary()

    # ------------------------------------------------------------------
    # /batch-stats
    # ------------------------------------------------------------------

    async def batch_stats_handler(args: str) -> str:
        from lidco.economics.batch_optimizer import BatchOptimizer

        if "batch_optimizer" not in _state:
            _state["batch_optimizer"] = BatchOptimizer()
        optimizer: BatchOptimizer = _state["batch_optimizer"]  # type: ignore[assignment]

        return optimizer.summary()

    registry.register(SlashCommand("budget", "Show budget status", budget_handler))
    registry.register(SlashCommand("cost-alerts", "List cost alert rules", cost_alerts_handler))
    registry.register(SlashCommand("model-optimizer", "Show model recommendations", model_optimizer_handler))
    registry.register(SlashCommand("batch-stats", "Show batch optimization stats", batch_stats_handler))
