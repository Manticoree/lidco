"""Q222 CLI commands: /tool-cache, /cache-stats, /cache-invalidate, /dedup-stats."""
from __future__ import annotations


def register(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q222 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /tool-cache
    # ------------------------------------------------------------------

    async def tool_cache_handler(args: str) -> str:
        from lidco.tools.result_cache import ToolResultCache

        cache = ToolResultCache()
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /tool-cache <tool_name> <args> [result]"
        if len(parts) < 2:
            return "Usage: /tool-cache <tool_name> <args> [result]"
        tool_name, tool_args = parts[0], parts[1]
        if len(parts) == 3:
            cache.put(tool_name, tool_args, parts[2])
            return f"Cached result for {tool_name}({tool_args})"
        result = cache.get(tool_name, tool_args)
        if result is None:
            return f"No cached result for {tool_name}({tool_args})"
        return result

    # ------------------------------------------------------------------
    # /cache-stats
    # ------------------------------------------------------------------

    async def cache_stats_handler(args: str) -> str:
        from lidco.tools.result_cache import ToolResultCache

        cache = ToolResultCache()
        return cache.summary()

    # ------------------------------------------------------------------
    # /cache-invalidate
    # ------------------------------------------------------------------

    async def cache_invalidate_handler(args: str) -> str:
        from lidco.tools.cache_invalidator import CacheInvalidator

        inv = CacheInvalidator()
        path = args.strip()
        if not path:
            return "Usage: /cache-invalidate <file_path>"
        event = inv.on_file_changed(path)
        return (
            f"Invalidated {len(event.affected_keys)} keys "
            f"for {event.path} ({event.reason})"
        )

    # ------------------------------------------------------------------
    # /dedup-stats
    # ------------------------------------------------------------------

    async def dedup_stats_handler(args: str) -> str:
        from lidco.tools.dedup_engine import DedupEngine

        engine = DedupEngine()
        return engine.summary()

    registry.register(
        SlashCommand("tool-cache", "Manage tool result cache", tool_cache_handler)
    )
    registry.register(
        SlashCommand("cache-stats", "Show cache statistics", cache_stats_handler)
    )
    registry.register(
        SlashCommand(
            "cache-invalidate",
            "Invalidate cache for file path",
            cache_invalidate_handler,
        )
    )
    registry.register(
        SlashCommand("dedup-stats", "Show dedup statistics", dedup_stats_handler)
    )
