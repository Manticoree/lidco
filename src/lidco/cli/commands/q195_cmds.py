"""Q195 CLI commands: /cache-stats, /cache-warm, /cache-clear, /token-optimize."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q195 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    _state: dict[str, object] = {}

    # ------------------------------------------------------------------
    # /cache-stats
    # ------------------------------------------------------------------

    async def cache_stats_handler(args: str) -> str:
        from lidco.cache.prompt_cache import PromptCache

        cache: PromptCache | None = _state.get("prompt_cache")  # type: ignore[assignment]
        if cache is None:
            cache = PromptCache()
            _state["prompt_cache"] = cache
        s = cache.stats
        return (
            f"Hits: {s.hits} | Misses: {s.misses} | "
            f"Evictions: {s.evictions} | Size: {s.size}"
        )

    # ------------------------------------------------------------------
    # /cache-warm
    # ------------------------------------------------------------------

    async def cache_warm_handler(args: str) -> str:
        from lidco.cache.cache_warmer import CacheWarmer
        from lidco.cache.prompt_cache import PromptCache

        cache: PromptCache | None = _state.get("prompt_cache")  # type: ignore[assignment]
        if cache is None:
            cache = PromptCache()
            _state["prompt_cache"] = cache

        parts = args.strip().split(maxsplit=1)
        if not parts or len(parts) < 2:
            return "Usage: /cache-warm <key> <value>"

        key = parts[0]
        value = parts[1]
        warmer = CacheWarmer(cache)
        result = warmer.warm(((key, value),))
        return f"Warmed: {result.warmed} | Skipped: {result.skipped} | Failed: {result.failed}"

    # ------------------------------------------------------------------
    # /cache-clear
    # ------------------------------------------------------------------

    async def cache_clear_handler(args: str) -> str:
        from lidco.cache.prompt_cache import PromptCache

        cache: PromptCache | None = _state.get("prompt_cache")  # type: ignore[assignment]
        if cache is None:
            return "Cache is empty."
        old_size = cache.stats.size
        cache.clear()
        return f"Cleared {old_size} entries."

    # ------------------------------------------------------------------
    # /token-optimize
    # ------------------------------------------------------------------

    async def token_optimize_handler(args: str) -> str:
        from lidco.cache.token_compressor import TokenCompressor

        text = args.strip()
        if not text:
            return "Usage: /token-optimize <text>"
        compressor = TokenCompressor()
        result = compressor.compress(text)
        return (
            f"Original: {result.original_tokens} tokens | "
            f"Compressed: {result.compressed_tokens} tokens | "
            f"Ratio: {result.ratio:.2%}"
        )

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------

    registry.register(SlashCommand("cache-stats", "Show prompt cache statistics", cache_stats_handler))
    registry.register(SlashCommand("cache-warm", "Pre-warm the prompt cache", cache_warm_handler))
    registry.register(SlashCommand("cache-clear", "Clear the prompt cache", cache_clear_handler))
    registry.register(SlashCommand("token-optimize", "Compress text to reduce tokens", token_optimize_handler))
