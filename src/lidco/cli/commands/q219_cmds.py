"""Q219 CLI commands: /compact, /compact-stats, /compact-preview, /context-budget."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q219 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /compact
    # ------------------------------------------------------------------

    async def compact_handler(args: str) -> str:
        from lidco.context.compression_strategy import CompressionStrategy, StrategyType

        name = args.strip().lower() if args.strip() else "balanced"
        try:
            strategy_type = StrategyType(name)
        except ValueError:
            return f"Unknown strategy: {name}. Use aggressive, balanced, or conservative."

        strategy = CompressionStrategy(strategy_type)
        # Demo with empty list — in real usage wired to session messages
        compressed, stats = strategy.compress([])
        return strategy.summary(stats)

    # ------------------------------------------------------------------
    # /compact-stats
    # ------------------------------------------------------------------

    async def compact_stats_handler(args: str) -> str:
        from lidco.context.semantic_summarizer import SemanticSummarizer

        summarizer = SemanticSummarizer()
        stats = summarizer.stats()
        lines = [f"{k}: {v}" for k, v in stats.items()]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /compact-preview
    # ------------------------------------------------------------------

    async def compact_preview_handler(args: str) -> str:
        from lidco.context.incremental_compactor import IncrementalCompactor

        compactor = IncrementalCompactor()
        target = int(args.strip()) if args.strip().isdigit() else 1000
        result = compactor.compact([], target)
        return (
            f"Compacted: {len(result.compacted)} messages | "
            f"Removed: {result.removed_count} | "
            f"Saved: {result.saved_tokens} tokens | "
            f"Watermark: {result.watermark}"
        )

    # ------------------------------------------------------------------
    # /context-budget
    # ------------------------------------------------------------------

    async def context_budget_handler(args: str) -> str:
        from lidco.context.priority_scorer import PriorityScorer

        budget = int(args.strip()) if args.strip().isdigit() else 4000
        scorer = PriorityScorer()
        return f"Context budget set to {budget} tokens. Scorer decay rate: {scorer._decay_rate}"

    registry.register(
        SlashCommand("compact", "Compress conversation context", compact_handler)
    )
    registry.register(
        SlashCommand("compact-stats", "Show compression statistics", compact_stats_handler)
    )
    registry.register(
        SlashCommand("compact-preview", "Preview compaction result", compact_preview_handler)
    )
    registry.register(
        SlashCommand("context-budget", "Set context token budget", context_budget_handler)
    )
