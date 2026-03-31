"""Q145 CLI commands: /history, /alias, /recent, /breadcrumb."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q145 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # --- /history ---
    async def history_handler(args: str) -> str:
        from lidco.ux.command_history import CommandHistory

        if "history" not in _state:
            _state["history"] = CommandHistory()
        hist: CommandHistory = _state["history"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "search":
            if not rest:
                return "Usage: /history search <query>"
            results = hist.search(rest)
            if not results:
                return f"No history entries matching '{rest}'."
            lines = [f"  {e.command} (success={e.success})" for e in results[:20]]
            return f"Search results ({len(results)}):\n" + "\n".join(lines)

        if sub == "frequent":
            freqs = hist.frequent(10)
            if not freqs:
                return "No history yet."
            lines = [f"  {cmd}: {cnt}" for cmd, cnt in freqs]
            return "Most frequent commands:\n" + "\n".join(lines)

        if sub == "clear":
            hist.clear()
            return "History cleared."

        if sub == "last":
            n = 10
            if rest:
                try:
                    n = int(rest)
                except ValueError:
                    pass
            entries = hist.last(n)
            if not entries:
                return "No history yet."
            lines = [f"  {e.command}" for e in entries]
            return f"Last {len(entries)} commands:\n" + "\n".join(lines)

        if sub == "undo":
            entry = hist.undo_last()
            if entry is None:
                return "Nothing to undo."
            return f"Undid: {entry.command}"

        return "Usage: /history search|frequent|clear|last|undo"

    # --- /alias ---
    async def alias_handler(args: str) -> str:
        from lidco.ux.command_alias import CommandAlias

        if "alias" not in _state:
            _state["alias"] = CommandAlias()
        aliases: CommandAlias = _state["alias"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "add":
            tokens = rest.split(maxsplit=2)
            if len(tokens) < 2:
                return "Usage: /alias add <name> <expansion> [description]"
            name = tokens[0]
            expansion = tokens[1]
            desc = tokens[2] if len(tokens) > 2 else ""
            aliases.add(name, expansion, desc)
            return f"Alias '{name}' -> '{expansion}' added."

        if sub == "remove":
            if not rest:
                return "Usage: /alias remove <name>"
            removed = aliases.remove(rest.strip())
            if removed:
                return f"Alias '{rest.strip()}' removed."
            return f"Alias '{rest.strip()}' not found."

        if sub == "list":
            all_aliases = aliases.list_aliases()
            if not all_aliases:
                return "No aliases defined."
            lines = [f"  {a.name} -> {a.expansion}" for a in all_aliases]
            return "Aliases:\n" + "\n".join(lines)

        return "Usage: /alias add|remove|list"

    # --- /recent ---
    async def recent_handler(args: str) -> str:
        from lidco.ux.recent_files import RecentFiles

        if "recent" not in _state:
            _state["recent"] = RecentFiles()
        recents: RecentFiles = _state["recent"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "files":
            files = recents.recent(10)
            if not files:
                return "No recent files."
            lines = [f"  {f.path} ({f.action}, {f.access_count}x)" for f in files]
            return "Recent files:\n" + "\n".join(lines)

        if sub == "search":
            if not rest:
                return "Usage: /recent search <pattern>"
            results = recents.search(rest)
            if not results:
                return f"No files matching '{rest}'."
            lines = [f"  {f.path} ({f.action})" for f in results[:20]]
            return f"Matching files ({len(results)}):\n" + "\n".join(lines)

        if sub == "frequent":
            files = recents.frequent(10)
            if not files:
                return "No recent files."
            lines = [f"  {f.path} ({f.access_count}x)" for f in files]
            return "Most accessed files:\n" + "\n".join(lines)

        if sub == "clear":
            recents.clear()
            return "Recent files cleared."

        return "Usage: /recent files|search|frequent|clear"

    # --- /breadcrumb ---
    async def breadcrumb_handler(args: str) -> str:
        from lidco.ux.breadcrumb import Breadcrumb

        if "breadcrumb" not in _state:
            _state["breadcrumb"] = Breadcrumb()
        bc: Breadcrumb = _state["breadcrumb"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "show":
            trail = bc.render()
            if not trail:
                return "Breadcrumb trail is empty."
            return f"Trail: {trail}"

        if sub == "back":
            n = 1
            if rest:
                try:
                    n = int(rest)
                except ValueError:
                    pass
            removed = bc.go_back(n)
            if not removed:
                return "Already at the start."
            labels = ", ".join(c.label for c in removed)
            return f"Went back {len(removed)} step(s): {labels}"

        if sub == "push":
            if not rest:
                return "Usage: /breadcrumb push <label> [context]"
            tokens = rest.split(maxsplit=1)
            label = tokens[0]
            ctx = tokens[1] if len(tokens) > 1 else ""
            bc.push(label, ctx)
            return f"Pushed: {label}"

        if sub == "clear":
            bc.clear()
            return "Breadcrumb trail cleared."

        return "Usage: /breadcrumb show|back|push|clear"

    registry.register(SlashCommand("history", "Command history search and navigation", history_handler))
    registry.register(SlashCommand("alias", "Command alias management", alias_handler))
    registry.register(SlashCommand("recent", "Recent files tracking", recent_handler))
    registry.register(SlashCommand("breadcrumb", "Breadcrumb navigation trail", breadcrumb_handler))
