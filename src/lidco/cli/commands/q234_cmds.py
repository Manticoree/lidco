"""Q234 CLI commands: /budget-history, /efficiency, /optimize-budget, /compare-budgets."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q234 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /budget-history
    # ------------------------------------------------------------------

    async def budget_history_handler(args: str) -> str:
        from lidco.budget.history import BudgetHistory

        history = BudgetHistory()
        if not args.strip():
            return history.summary()
        parts = args.strip().split()
        cmd = parts[0]
        if cmd == "record" and len(parts) >= 2:
            sid = parts[1]
            model = parts[2] if len(parts) > 2 else ""
            tokens = int(parts[3]) if len(parts) > 3 else 0
            snap = history.record(sid, model=model, total_tokens=tokens)
            return f"Recorded snapshot for session {snap.session_id}."
        if cmd == "export":
            data = history.export()
            return f"Exported {len(data)} snapshots."
        return history.summary()

    # ------------------------------------------------------------------
    # /efficiency
    # ------------------------------------------------------------------

    async def efficiency_handler(args: str) -> str:
        from lidco.budget.efficiency import EfficiencyScorer

        scorer = EfficiencyScorer()
        if not args.strip():
            return "Usage: /efficiency <total_tokens> [useful_tokens] [compaction_savings] [tool_waste]"
        parts = args.strip().split()
        total = int(parts[0])
        useful = int(parts[1]) if len(parts) > 1 else 0
        compaction = int(parts[2]) if len(parts) > 2 else 0
        waste = int(parts[3]) if len(parts) > 3 else 0
        result = scorer.score(total, useful, compaction, waste)
        return scorer.summary(result)

    # ------------------------------------------------------------------
    # /optimize-budget
    # ------------------------------------------------------------------

    async def optimize_budget_handler(args: str) -> str:
        from lidco.budget.optimization_advisor import OptimizationAdvisor

        advisor = OptimizationAdvisor()
        if not args.strip():
            return "Usage: /optimize-budget <total_tokens> <context_limit> <compactions> [turns]"
        parts = args.strip().split()
        total = int(parts[0])
        limit = int(parts[1]) if len(parts) > 1 else 128000
        compactions = int(parts[2]) if len(parts) > 2 else 0
        turns = int(parts[3]) if len(parts) > 3 else 0
        advisor.analyze(total, limit, compactions, turns=turns)
        return advisor.summary()

    # ------------------------------------------------------------------
    # /compare-budgets
    # ------------------------------------------------------------------

    async def compare_budgets_handler(args: str) -> str:
        from lidco.budget.ab_comparator import ABComparator

        comparator = ABComparator()
        if not args.strip():
            return "Usage: /compare-budgets <labelA> <tokA> <effA> <costA> <labelB> <tokB> <effB> <costB>"
        parts = args.strip().split()
        if len(parts) < 8:
            return "Need 8 args: labelA tokensA effA costA labelB tokensB effB costB"
        result = comparator.compare(
            parts[0], int(parts[1]), float(parts[2]), float(parts[3]),
            parts[4], int(parts[5]), float(parts[6]), float(parts[7]),
        )
        return comparator.summary(result)

    registry.register(SlashCommand("budget-history", "View budget usage history", budget_history_handler))
    registry.register(SlashCommand("efficiency", "Score session token efficiency", efficiency_handler))
    registry.register(SlashCommand("optimize-budget", "Get budget optimization recommendations", optimize_budget_handler))
    registry.register(SlashCommand("compare-budgets", "A/B compare budget efficiency", compare_budgets_handler))
