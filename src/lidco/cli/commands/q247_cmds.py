"""Q247 CLI commands: /parse-response, /validate-response, /transform, /response-cache."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q247 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /parse-response
    # ------------------------------------------------------------------

    async def parse_response_handler(args: str) -> str:
        from lidco.response.parser import ResponseParser

        parser = ResponseParser()
        text = args.strip()
        if not text:
            return "Usage: /parse-response <response text>"
        parsed = parser.parse(text)
        lines = [
            f"Text blocks: {len(parsed.text_blocks)}",
            f"Code blocks: {len(parsed.code_blocks)}",
            f"Tool calls:  {len(parsed.tool_calls)}",
            f"Thinking:    {'yes' if parsed.thinking else 'no'}",
        ]
        for i, cb in enumerate(parsed.code_blocks):
            lines.append(f"  Code[{i}] lang={cb['language']}")
        for i, tc in enumerate(parsed.tool_calls):
            lines.append(f"  Tool[{i}] name={tc['name']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /validate-response
    # ------------------------------------------------------------------

    async def validate_response_handler(args: str) -> str:
        from lidco.response.validator import ResponseValidator

        validator = ResponseValidator()
        text = args.strip()
        if not text:
            return "Usage: /validate-response <response text>"
        result = validator.validate(text)
        if result.is_valid:
            return "Validation passed."
        return "Issues:\n" + "\n".join(f"- {i}" for i in result.issues)

    # ------------------------------------------------------------------
    # /transform
    # ------------------------------------------------------------------

    async def transform_handler(args: str) -> str:
        from lidco.response.transformer import ResponseTransformer

        transformer = ResponseTransformer()
        text = args.strip()
        if not text:
            return "Usage: /transform <response text>"
        return transformer.transform(text)

    # ------------------------------------------------------------------
    # /response-cache
    # ------------------------------------------------------------------

    async def response_cache_handler(args: str) -> str:
        from lidco.response.cache import ResponseCache

        cache = ResponseCache()
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "put":
            if len(parts) < 3:
                return "Usage: /response-cache put <prompt> <response>"
            cache.put(parts[1], parts[2])
            return "Cached."

        if sub == "get":
            if len(parts) < 2:
                return "Usage: /response-cache get <prompt>"
            hit = cache.get(parts[1])
            return hit if hit is not None else "Cache miss."

        if sub == "stats":
            s = cache.stats()
            return f"hits={s['hits']} misses={s['misses']} size={s['size']}"

        if sub == "clear":
            cache.clear()
            return "Cache cleared."

        return (
            "Usage: /response-cache <subcommand>\n"
            "  put <prompt> <response> — store entry\n"
            "  get <prompt>            — exact lookup\n"
            "  stats                   — show statistics\n"
            "  clear                   — clear all entries"
        )

    registry.register(SlashCommand("parse-response", "Parse LLM response structure", parse_response_handler))
    registry.register(SlashCommand("validate-response", "Validate response completeness", validate_response_handler))
    registry.register(SlashCommand("transform", "Transform response text", transform_handler))
    registry.register(SlashCommand("response-cache", "Response caching operations", response_cache_handler))
