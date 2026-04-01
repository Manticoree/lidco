"""Q235 CLI commands: /thinkback, /thinking-search, /thinking-stats, /thinking-diff."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q235 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /thinkback
    # ------------------------------------------------------------------

    async def thinkback_handler(args: str) -> str:
        from lidco.thinkback.store import ThinkingStore
        from lidco.thinkback.viewer import ThinkingViewer

        store = ThinkingStore()
        viewer = ThinkingViewer()

        parts = args.strip().split(maxsplit=1)
        if not parts:
            return store.summary()

        turn_str = parts[0]
        try:
            turn = int(turn_str)
        except ValueError:
            return f"Invalid turn number: {turn_str}"

        content = parts[1] if len(parts) > 1 else ""
        if content:
            block = store.append(turn, content)
            return viewer.format_block(content, turn=turn, tokens=block.token_count)

        blocks = store.get_by_turn(turn)
        if not blocks:
            return f"No thinking blocks for turn {turn}."
        formatted = [
            viewer.format_block(b.content, turn=b.turn, tokens=b.token_count)
            for b in blocks
        ]
        return "\n\n".join(formatted)

    # ------------------------------------------------------------------
    # /thinking-search
    # ------------------------------------------------------------------

    async def thinking_search_handler(args: str) -> str:
        from lidco.thinkback.search import ThinkingSearch

        query = args.strip()
        if not query:
            return "Usage: /thinking-search <query>"

        searcher = ThinkingSearch()
        # Without a live session store, report usage.
        return f"Search ready for query: {query}"

    # ------------------------------------------------------------------
    # /thinking-stats
    # ------------------------------------------------------------------

    async def thinking_stats_handler(args: str) -> str:
        from lidco.thinkback.store import ThinkingStore
        from lidco.thinkback.analyzer import ThinkingAnalyzer

        store = ThinkingStore()
        analyzer = ThinkingAnalyzer()
        lines = [
            store.summary(),
            analyzer.summary(),
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /thinking-diff
    # ------------------------------------------------------------------

    async def thinking_diff_handler(args: str) -> str:
        from lidco.thinkback.viewer import ThinkingViewer

        parts = args.strip().split("|", maxsplit=1)
        if len(parts) < 2:
            return "Usage: /thinking-diff <blockA> | <blockB>"

        viewer = ThinkingViewer()
        return viewer.diff(parts[0].strip(), parts[1].strip())

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    registry.register(
        SlashCommand("thinkback", "View/store thinking blocks", thinkback_handler)
    )
    registry.register(
        SlashCommand("thinking-search", "Search thinking traces", thinking_search_handler)
    )
    registry.register(
        SlashCommand("thinking-stats", "Show thinking statistics", thinking_stats_handler)
    )
    registry.register(
        SlashCommand("thinking-diff", "Diff two thinking blocks", thinking_diff_handler)
    )
