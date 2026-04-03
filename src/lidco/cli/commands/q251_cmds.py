"""Q251 CLI commands: /complete, /fill-middle, /snippet, /resolve-import."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q251 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /complete
    # ------------------------------------------------------------------

    async def complete_handler(args: str) -> str:
        from lidco.completion.engine import CompletionEngine

        engine = CompletionEngine()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "prefix":
            if not rest:
                return "Usage: /complete prefix <text>"
            items = engine.complete(rest)
            if not items:
                return "No completions found."
            lines = [f"{it.text} ({it.kind}, score={it.score})" for it in items]
            return "\n".join(lines)

        if sub == "stats":
            s = engine.stats()
            return f"symbols={s['symbols']} queries={s['queries']} context_keys={s['context_keys']}"

        return (
            "Usage: /complete <subcommand>\n"
            "  prefix <text> — show completions for prefix\n"
            "  stats         — show engine statistics"
        )

    # ------------------------------------------------------------------
    # /fill-middle
    # ------------------------------------------------------------------

    async def fill_middle_handler(args: str) -> str:
        from lidco.completion.fim import FillInMiddle

        fim = FillInMiddle()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "fill":
            if not rest:
                return "Usage: /fill-middle fill <prefix>|||<suffix>"
            if "|||" in rest:
                prefix, suffix = rest.split("|||", 1)
            else:
                prefix, suffix = rest, ""
            result = fim.fill(prefix, suffix)
            return result if result else "(empty fill)"

        if sub == "suggest":
            if not rest:
                return "Usage: /fill-middle suggest <prefix>|||<suffix>"
            if "|||" in rest:
                prefix, suffix = rest.split("|||", 1)
            else:
                prefix, suffix = rest, ""
            suggestions = fim.suggest(prefix, suffix)
            if not suggestions:
                return "No suggestions."
            return "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(suggestions))

        if sub == "indent":
            if not rest:
                return "Usage: /fill-middle indent <text>"
            detected = fim.detect_indent(rest)
            return f"Detected indent: {repr(detected)}"

        return (
            "Usage: /fill-middle <subcommand>\n"
            "  fill <prefix>|||<suffix>    — generate fill\n"
            "  suggest <prefix>|||<suffix> — multiple suggestions\n"
            "  indent <text>               — detect indentation"
        )

    # ------------------------------------------------------------------
    # /snippet
    # ------------------------------------------------------------------

    async def snippet_handler(args: str) -> str:
        from lidco.completion.snippets import Snippet, SnippetExpander

        expander = SnippetExpander()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "expand":
            if not rest:
                return "Usage: /snippet expand <trigger>"
            result = expander.expand(rest)
            return result if result is not None else f"No snippet for trigger '{rest}'."

        if sub == "list":
            items = expander.list_all()
            if not items:
                return "No snippets registered."
            return "\n".join(f"  {s.trigger} — {s.description or s.name}" for s in items)

        if sub == "search":
            if not rest:
                return "Usage: /snippet search <query>"
            found = expander.search(rest)
            if not found:
                return "No matching snippets."
            return "\n".join(f"  {s.trigger} — {s.name}" for s in found)

        return (
            "Usage: /snippet <subcommand>\n"
            "  expand <trigger> — expand a snippet\n"
            "  list             — list all snippets\n"
            "  search <query>   — search snippets"
        )

    # ------------------------------------------------------------------
    # /resolve-import
    # ------------------------------------------------------------------

    async def resolve_import_handler(args: str) -> str:
        from lidco.completion.import_resolver import ImportResolver

        resolver = ImportResolver()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "resolve":
            if not rest:
                return "Usage: /resolve-import resolve <symbol>"
            paths = resolver.resolve(rest)
            if not paths:
                return f"No modules export '{rest}'."
            return "\n".join(f"  {p}" for p in paths)

        if sub == "suggest":
            if not rest:
                return "Usage: /resolve-import suggest <symbol>"
            stmt = resolver.suggest(rest)
            return stmt if stmt else f"No import suggestion for '{rest}'."

        if sub == "missing":
            if not rest:
                return "Usage: /resolve-import missing <source>"
            missing = resolver.detect_missing(rest)
            if not missing:
                return "No missing imports detected."
            return "Missing: " + ", ".join(missing)

        return (
            "Usage: /resolve-import <subcommand>\n"
            "  resolve <symbol> — find modules exporting symbol\n"
            "  suggest <symbol> — suggest import statement\n"
            "  missing <source> — detect missing imports"
        )

    registry.register(SlashCommand("complete", "Intelligent code completion", complete_handler))
    registry.register(SlashCommand("fill-middle", "Fill-in-the-middle completion", fill_middle_handler))
    registry.register(SlashCommand("snippet", "Snippet expansion", snippet_handler))
    registry.register(SlashCommand("resolve-import", "Import resolution", resolve_import_handler))
