"""Q229 CLI commands: /task-score, /budget-scale, /estimate-cost, /budget-forecast."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q229 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /task-score
    # ------------------------------------------------------------------
    async def task_score_handler(args: str) -> str:
        from lidco.budget.task_scorer import TaskScorer

        prompt = args.strip()
        if not prompt:
            return "Usage: /task-score <prompt text>"
        scorer = TaskScorer()
        result = scorer.score(prompt)
        return scorer.summary(result)

    # ------------------------------------------------------------------
    # /budget-scale
    # ------------------------------------------------------------------
    async def budget_scale_handler(args: str) -> str:
        from lidco.budget.dynamic_scaler import DynamicScaler

        parts = args.strip().split()
        if not parts:
            return "Usage: /budget-scale <complexity_score> [base_tokens]"
        try:
            complexity_score = float(parts[0])
        except ValueError:
            return "Error: complexity_score must be a number"
        base = int(parts[1]) if len(parts) > 1 else 4096
        scaler = DynamicScaler()
        decision = scaler.scale(complexity_score, base)
        return (
            f"Scale: {decision.requested} -> {decision.adjusted} "
            f"(score={decision.complexity_score:.2f}, {decision.reason})"
        )

    # ------------------------------------------------------------------
    # /estimate-cost
    # ------------------------------------------------------------------
    async def estimate_cost_handler(args: str) -> str:
        from lidco.budget.pre_call_estimator import PreCallEstimator

        parts = args.strip().split()
        if not parts:
            return "Usage: /estimate-cost <tool_name> [budget_remaining]"
        tool_name = parts[0]
        budget = int(parts[1]) if len(parts) > 1 else 100_000
        estimator = PreCallEstimator()
        est = estimator.estimate(tool_name, budget_remaining=budget)
        return (
            f"Estimate: {est.tool_name} ~{est.estimated_tokens} tokens "
            f"(confidence={est.confidence:.0%}, "
            f"within_budget={est.within_budget})"
        )

    # ------------------------------------------------------------------
    # /budget-forecast
    # ------------------------------------------------------------------
    async def budget_forecast_handler(args: str) -> str:
        from lidco.budget.budget_forecaster import BudgetForecaster

        parts = args.strip().split()
        budget = int(parts[0]) if parts else 128_000
        forecaster = BudgetForecaster(total_budget=budget)
        return forecaster.summary()

    registry.register(
        SlashCommand("task-score", "Score task complexity from prompt", task_score_handler)
    )
    registry.register(
        SlashCommand("budget-scale", "Scale token budget by complexity", budget_scale_handler)
    )
    registry.register(
        SlashCommand("estimate-cost", "Estimate tool call token cost", estimate_cost_handler)
    )
    registry.register(
        SlashCommand("budget-forecast", "Forecast token budget depletion", budget_forecast_handler)
    )
