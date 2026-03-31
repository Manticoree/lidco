"""Q161 CLI commands: /continuation, /tools-lazy, /tool-search."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q161 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /continuation [on|off|status]
    # ------------------------------------------------------------------

    async def continuation_handler(args: str) -> str:
        from lidco.llm.continuation_config import ContinuationConfig

        if "cont_config" not in _state:
            _state["cont_config"] = ContinuationConfig()

        config: ContinuationConfig = _state["cont_config"]  # type: ignore[assignment]
        sub = args.strip().lower()

        if sub == "on":
            config.enabled = True
            return "Prefill continuation enabled."
        if sub == "off":
            config.enabled = False
            return "Prefill continuation disabled."
        if sub in ("status", ""):
            return (
                f"Continuation: {'enabled' if config.enabled else 'disabled'}\n"
                f"Max continuations: {config.max_continuations}\n"
                f"Code truncation detection: {'on' if config.detect_code_truncation else 'off'}"
            )

        return (
            "Usage: /continuation [on|off|status]\n"
            "  on     — enable prefill continuation\n"
            "  off    — disable prefill continuation\n"
            "  status — show current settings (default)"
        )

    # ------------------------------------------------------------------
    # /tools-lazy [status|resolve <name>|search <query>]
    # ------------------------------------------------------------------

    async def tools_lazy_handler(args: str) -> str:
        from lidco.tools.lazy_registry import LazyToolRegistry

        if "lazy_registry" not in _state:
            _state["lazy_registry"] = LazyToolRegistry()

        reg: LazyToolRegistry = _state["lazy_registry"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "status" or sub == "":
            s = reg.stats()
            names = reg.list_names()
            lines = [
                f"Total tools: {s['total']}",
                f"Resolved: {s['resolved']}",
                f"Pending: {s['pending']}",
            ]
            if names:
                lines.append(f"Tools: {', '.join(names)}")
            return "\n".join(lines)

        if sub == "resolve":
            if not rest:
                return "Usage: /tools-lazy resolve <name>"
            schema = reg.resolve(rest)
            if schema is None:
                return f"Tool '{rest}' not found."
            return json.dumps(schema, indent=2)

        if sub == "search":
            if not rest:
                return "Usage: /tools-lazy search <query>"
            results = reg.search(rest)
            if not results:
                return f"No tools matching '{rest}'."
            lines = [f"  {e.name} — {e.description}" for e in results]
            return f"Found {len(results)} tool(s):\n" + "\n".join(lines)

        return (
            "Usage: /tools-lazy <subcommand>\n"
            "  status           — show registry stats\n"
            "  resolve <name>   — resolve full schema for a tool\n"
            "  search <query>   — search tools by keyword"
        )

    # ------------------------------------------------------------------
    # /tool-search <query>
    # ------------------------------------------------------------------

    async def tool_search_handler(args: str) -> str:
        from lidco.tools.lazy_registry import LazyToolRegistry

        if "lazy_registry" not in _state:
            _state["lazy_registry"] = LazyToolRegistry()

        reg: LazyToolRegistry = _state["lazy_registry"]  # type: ignore[assignment]
        query = args.strip()
        if not query:
            return "Usage: /tool-search <query>"

        results = reg.search(query)
        if not results:
            return f"No tools matching '{query}'."
        lines = [f"  {e.name} — {e.description}" for e in results]
        return f"Found {len(results)} tool(s):\n" + "\n".join(lines)

    registry.register(SlashCommand("continuation", "Toggle prefill continuation", continuation_handler))
    registry.register(SlashCommand("tools-lazy", "Lazy tool registry management", tools_lazy_handler))
    registry.register(SlashCommand("tool-search", "Search tools by keyword", tool_search_handler))
