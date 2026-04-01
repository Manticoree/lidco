"""Q228 CLI commands: /auto-compact, /compaction-log, /compact-tools, /compaction-config."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q228 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /auto-compact
    # ------------------------------------------------------------------

    async def auto_compact_handler(args: str) -> str:
        from lidco.budget.compaction_orchestrator import (
            CompactionOrchestrator,
            CompactionTrigger,
        )

        parts = args.strip().split()
        if not parts:
            return "Usage: /auto-compact <utilization 0-1>"
        try:
            util = float(parts[0])
        except ValueError:
            return "Error: utilization must be a number between 0 and 1."
        orch = CompactionOrchestrator()
        trigger = orch.should_compact(util)
        if trigger is None:
            return f"Utilization {util:.0%}: no compaction needed."
        strategy = orch.select_strategy(util)
        orch.record_compaction(trigger, before=1000, after=500, strategy=strategy)
        return f"Trigger: {trigger.value} | Strategy: {strategy} | {orch.summary()}"

    # ------------------------------------------------------------------
    # /compaction-log
    # ------------------------------------------------------------------

    async def compaction_log_handler(args: str) -> str:
        from lidco.budget.compaction_journal import CompactionJournal

        journal = CompactionJournal()
        if args.strip() == "clear":
            journal.clear()
            return "Journal cleared."
        return journal.summary()

    # ------------------------------------------------------------------
    # /compact-tools
    # ------------------------------------------------------------------

    async def compact_tools_handler(args: str) -> str:
        from lidco.budget.tool_compressor import ToolCompressor

        tc = ToolCompressor()
        if not args.strip():
            return tc.summary()
        parts = args.strip().split(maxsplit=1)
        tool_name = parts[0]
        content = parts[1] if len(parts) > 1 else ""
        compressed, stats = tc.compress(tool_name, content)
        return (
            f"Tool: {stats.tool_name} | "
            f"Original: {stats.original_tokens} | "
            f"Compressed: {stats.compressed_tokens} | "
            f"Truncated: {stats.truncated}"
        )

    # ------------------------------------------------------------------
    # /compaction-config
    # ------------------------------------------------------------------

    async def compaction_config_handler(args: str) -> str:
        from lidco.budget.strategy_selector import StrategySelector

        selector = StrategySelector()
        if args.strip():
            try:
                util = float(args.strip())
            except ValueError:
                return "Error: provide a utilization number (0-1)."
            config = selector.select(util)
            return (
                f"Pressure: {config.pressure.value} | Strategy: {config.name} | "
                f"Keep recent: {config.keep_recent} | Summarize: {config.summarize_older}"
            )
        return selector.summary()

    registry.register(
        SlashCommand("auto-compact", "Auto-compact context window", auto_compact_handler)
    )
    registry.register(
        SlashCommand("compaction-log", "View compaction journal", compaction_log_handler)
    )
    registry.register(
        SlashCommand("compact-tools", "Compress tool results", compact_tools_handler)
    )
    registry.register(
        SlashCommand(
            "compaction-config", "View compaction strategy config", compaction_config_handler
        )
    )
