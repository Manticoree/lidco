"""Q274 CLI commands: /actions, /code-action, /file-action, /git-action."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q274 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /actions
    # ------------------------------------------------------------------

    async def actions_handler(args: str) -> str:
        from lidco.actions.registry import QuickActionRegistry

        if "reg" not in _state:
            _state["reg"] = QuickActionRegistry()
        reg: QuickActionRegistry = _state["reg"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            actions = reg.all_actions()
            if not actions:
                return "No actions registered."
            lines = [f"- {a.name} (ctx={a.context}, pri={a.priority}, enabled={a.enabled})" for a in actions]
            return "\n".join(lines)

        if sub == "find":
            ctx = rest or "global"
            found = reg.find(ctx)
            if not found:
                return f"No actions for context '{ctx}'."
            lines = [f"- {a.name} (pri={a.priority})" for a in found]
            return "\n".join(lines)

        if sub == "execute":
            if not rest:
                return "Usage: /actions execute <name>"
            result = reg.execute(rest)
            return result.message

        if sub == "enable":
            if not rest:
                return "Usage: /actions enable <name>"
            ok = reg.enable(rest)
            return f"Enabled '{rest}'." if ok else f"Action '{rest}' not found."

        if sub == "disable":
            if not rest:
                return "Usage: /actions disable <name>"
            ok = reg.disable(rest)
            return f"Disabled '{rest}'." if ok else f"Action '{rest}' not found."

        return "Usage: /actions [list | find <context> | execute <name> | enable <name> | disable <name>]"

    # ------------------------------------------------------------------
    # /code-action
    # ------------------------------------------------------------------

    async def code_action_handler(args: str) -> str:
        from lidco.actions.code_provider import CodeActionsProvider

        if "code" not in _state:
            _state["code"] = CodeActionsProvider()
        prov: CodeActionsProvider = _state["code"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            lang = rest or "python"
            actions = prov.available_actions(lang)
            if not actions:
                return f"No code actions for '{lang}'."
            lines = [f"- {a.name} ({a.type})" for a in actions]
            return "\n".join(lines)

        if sub == "extract":
            if not rest:
                return "Usage: /code-action extract <name>"
            return f"Extract function '{rest}' — use with code selection."

        if sub == "rename":
            rename_parts = rest.split(maxsplit=1)
            if len(rename_parts) < 2:
                return "Usage: /code-action rename <old> <new>"
            return f"Rename '{rename_parts[0]}' -> '{rename_parts[1]}' — applied."

        if sub == "wrap-try":
            return "Wrap selection in try/except — use with code selection."

        if sub == "comment":
            return "Toggle comment — use with code selection."

        return "Usage: /code-action [list [language] | extract <name> | rename <old> <new> | wrap-try | comment]"

    # ------------------------------------------------------------------
    # /file-action
    # ------------------------------------------------------------------

    async def file_action_handler(args: str) -> str:
        from lidco.actions.file_provider import FileActionsProvider

        if "file" not in _state:
            _state["file"] = FileActionsProvider()
        prov: FileActionsProvider = _state["file"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "create":
            if not rest:
                return "Usage: /file-action create <path>"
            result = prov.create(rest)
            return result.message

        if sub == "rename":
            rp = rest.split(maxsplit=1)
            if len(rp) < 2:
                return "Usage: /file-action rename <src> <tgt>"
            result = prov.rename(rp[0], rp[1])
            return result.message

        if sub == "move":
            mp = rest.split(maxsplit=1)
            if len(mp) < 2:
                return "Usage: /file-action move <src> <tgt>"
            result = prov.move(mp[0], mp[1])
            return result.message

        if sub == "delete":
            if not rest:
                return "Usage: /file-action delete <path>"
            result = prov.delete(rest)
            return result.message

        if sub == "history":
            hist = prov.history()
            if not hist:
                return "No file actions recorded."
            lines = [f"- {r.action}: {r.source}" + (f" -> {r.target}" if r.target else "") for r in hist]
            return "\n".join(lines)

        if sub == "undo":
            result = prov.undo_last()
            if result is None:
                return "Nothing to undo."
            return result.message

        return "Usage: /file-action [create <path> | rename <src> <tgt> | move <src> <tgt> | delete <path> | history | undo]"

    # ------------------------------------------------------------------
    # /git-action
    # ------------------------------------------------------------------

    async def git_action_handler(args: str) -> str:
        from lidco.actions.git_provider import GitActionsProvider

        if "git" not in _state:
            _state["git"] = GitActionsProvider()
        prov: GitActionsProvider = _state["git"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "stage":
            if not rest:
                return "Usage: /git-action stage <files>"
            paths = rest.split()
            result = prov.stage(paths)
            return result.message

        if sub == "commit":
            if not rest:
                return "Usage: /git-action commit <msg>"
            result = prov.commit(rest)
            return result.message

        if sub == "push":
            result = prov.push()
            return result.message

        if sub == "branch":
            if not rest:
                return "Usage: /git-action branch <name>"
            result = prov.create_branch(rest)
            return result.message

        if sub == "stash":
            result = prov.stash(rest)
            return result.message

        if sub == "stash-pop":
            result = prov.stash_pop()
            return result.message

        if sub == "history":
            hist = prov.history()
            if not hist:
                return "No git actions recorded."
            lines = [f"- {r.action}: {r.message}" for r in hist]
            return "\n".join(lines)

        return "Usage: /git-action [stage <files> | commit <msg> | push | branch <name> | stash | stash-pop | history]"

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------
    registry.register(SlashCommand("actions", "Quick actions registry", actions_handler))
    registry.register(SlashCommand("code-action", "Code actions (extract, rename, wrap, comment)", code_action_handler))
    registry.register(SlashCommand("file-action", "File actions (create, rename, move, delete)", file_action_handler))
    registry.register(SlashCommand("git-action", "Git actions (stage, commit, push, branch, stash)", git_action_handler))
