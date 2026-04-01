"""Q232 CLI commands: /tool-budget, /tool-stats, /truncation-config, /result-limits."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q232 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /tool-budget
    # ------------------------------------------------------------------

    async def tool_budget_handler(args: str) -> str:
        from lidco.budget.tool_gate import ToolBudgetGate

        parts = args.strip().split()
        budget = int(parts[0]) if parts else 100_000
        warn = int(parts[1]) if len(parts) > 1 else 5_000
        gate = ToolBudgetGate(budget_remaining=budget, warn_threshold=warn)
        return gate.summary()

    # ------------------------------------------------------------------
    # /tool-stats
    # ------------------------------------------------------------------

    async def tool_stats_handler(args: str) -> str:
        from lidco.budget.tool_tracker import ToolTokenTracker

        tracker = ToolTokenTracker()
        if not args.strip():
            return "Usage: /tool-stats <tool> <input_tokens> <output_tokens>"
        parts = args.strip().split()
        name = parts[0]
        inp = int(parts[1]) if len(parts) > 1 else 0
        out = int(parts[2]) if len(parts) > 2 else 0
        tracker.record(name, input_tokens=inp, output_tokens=out)
        return tracker.summary()

    # ------------------------------------------------------------------
    # /truncation-config
    # ------------------------------------------------------------------

    async def truncation_config_handler(args: str) -> str:
        from lidco.budget.adaptive_truncator import AdaptiveTruncator

        truncator = AdaptiveTruncator()
        parts = args.strip().split()
        if len(parts) >= 2:
            truncator.set_limit(parts[0], int(parts[1]))
        return truncator.summary()

    # ------------------------------------------------------------------
    # /result-limits
    # ------------------------------------------------------------------

    async def result_limits_handler(args: str) -> str:
        from lidco.budget.result_limiter import ResultLimiter

        limiter = ResultLimiter()
        return limiter.summary()

    registry.register(SlashCommand("tool-budget", "Show/set budget gate", tool_budget_handler))
    registry.register(SlashCommand("tool-stats", "Record and display tool token stats", tool_stats_handler))
    registry.register(SlashCommand("truncation-config", "Show/set truncation config", truncation_config_handler))
    registry.register(SlashCommand("result-limits", "Show result limiter config", result_limits_handler))
