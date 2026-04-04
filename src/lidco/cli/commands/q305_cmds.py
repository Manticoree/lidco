"""Q305 CLI commands — /git-hooks, /hook-library, /compose-hooks, /hook-stats

Registered via register_q305_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q305_commands(registry) -> None:
    """Register Q305 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /git-hooks — manage git hooks v2
    # ------------------------------------------------------------------
    async def git_hooks_handler(args: str) -> str:
        """
        Usage: /git-hooks list
               /git-hooks install <type> <script>
               /git-hooks uninstall <type>
               /git-hooks run <type>
        """
        from lidco.githooks.manager import HookManagerV2, HookType

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /git-hooks <subcommand>\n"
                "  list                  list installed hooks\n"
                "  install <type> <script>  install a hook\n"
                "  uninstall <type>      remove a hook\n"
                "  run <type>            run a hook manually"
            )

        subcmd = parts[0].lower()

        def _resolve_type(name: str) -> HookType:
            name_upper = name.upper().replace("-", "_")
            return HookType[name_upper]

        mgr = HookManagerV2()

        if subcmd == "list":
            installed = mgr.list_installed()
            if not installed:
                return "No hooks installed."
            return "Installed hooks:\n" + "\n".join(f"  {h.value}" for h in installed)

        if subcmd == "install":
            if len(parts) < 3:
                return "Error: Usage: /git-hooks install <type> <script>"
            try:
                ht = _resolve_type(parts[1])
            except KeyError:
                return f"Error: Unknown hook type '{parts[1]}'. Valid: {', '.join(t.value for t in HookType)}"
            script = " ".join(parts[2:])
            mgr.install(ht, script)
            return f"Hook '{ht.value}' installed."

        if subcmd == "uninstall":
            if len(parts) < 2:
                return "Error: Usage: /git-hooks uninstall <type>"
            try:
                ht = _resolve_type(parts[1])
            except KeyError:
                return f"Error: Unknown hook type '{parts[1]}'."
            removed = mgr.uninstall(ht)
            if removed:
                return f"Hook '{ht.value}' removed."
            return f"Hook '{ht.value}' was not installed."

        if subcmd == "run":
            if len(parts) < 2:
                return "Error: Usage: /git-hooks run <type>"
            try:
                ht = _resolve_type(parts[1])
            except KeyError:
                return f"Error: Unknown hook type '{parts[1]}'."
            result = mgr.run(ht, args=parts[2:])
            status = "PASS" if result.success else "FAIL"
            out = f"[{status}] {ht.value} (exit={result.exit_code}, {result.duration:.2f}s)"
            if result.stdout:
                out += f"\n{result.stdout.rstrip()}"
            if result.stderr:
                out += f"\n{result.stderr.rstrip()}"
            return out

        return f"Unknown subcommand '{subcmd}'. Try /git-hooks without arguments for help."

    # ------------------------------------------------------------------
    # /hook-library — browse built-in hooks
    # ------------------------------------------------------------------
    async def hook_library_handler(args: str) -> str:
        """
        Usage: /hook-library [list|categories|get <name>|lang <language>]
        """
        from lidco.githooks.library import HookLibrary

        parts = shlex.split(args) if args.strip() else []
        lib = HookLibrary()

        if not parts or parts[0].lower() == "list":
            hooks = lib.builtin_hooks()
            if not hooks:
                return "No hooks in library."
            lines = [f"  {h.name} [{h.type.value}] — {h.description}" for h in hooks]
            return "Hook Library:\n" + "\n".join(lines)

        subcmd = parts[0].lower()

        if subcmd == "categories":
            cats = lib.categories()
            return "Categories:\n" + "\n".join(f"  {c}" for c in cats)

        if subcmd == "get":
            if len(parts) < 2:
                return "Error: Usage: /hook-library get <name>"
            h = lib.get(parts[1])
            if h is None:
                return f"Hook '{parts[1]}' not found."
            return (
                f"Name: {h.name}\nType: {h.type.value}\nCategory: {h.category}\n"
                f"Language: {h.language or '(any)'}\nDescription: {h.description}\n"
                f"Script:\n{h.script}"
            )

        if subcmd == "lang":
            if len(parts) < 2:
                return "Error: Usage: /hook-library lang <language>"
            hooks = lib.hooks_for_language(parts[1])
            if not hooks:
                return f"No hooks for language '{parts[1]}'."
            lines = [f"  {h.name} — {h.description}" for h in hooks]
            return f"Hooks for {parts[1]}:\n" + "\n".join(lines)

        return "Unknown subcommand. Try /hook-library without arguments for help."

    # ------------------------------------------------------------------
    # /compose-hooks — compose multiple hooks into one
    # ------------------------------------------------------------------
    async def compose_hooks_handler(args: str) -> str:
        """
        Usage: /compose-hooks <hook_type> <name1> [name2 ...]
        """
        from lidco.githooks.composer import HookComposer
        from lidco.githooks.library import HookLibrary
        from lidco.githooks.manager import HookType

        parts = shlex.split(args) if args.strip() else []
        if len(parts) < 2:
            return (
                "Usage: /compose-hooks <hook_type> <name1> [name2 ...]\n"
                "Compose library hooks into a single script for the given type."
            )

        type_str = parts[0].upper().replace("-", "_")
        try:
            ht = HookType[type_str]
        except KeyError:
            return f"Error: Unknown hook type '{parts[0]}'."

        lib = HookLibrary()
        composer = HookComposer()
        missing: list[str] = []
        for i, name in enumerate(parts[1:]):
            hook_def = lib.get(name)
            if hook_def is None:
                missing.append(name)
                continue
            composer.add(hook_def, order=i)

        if missing:
            return f"Error: Hooks not found: {', '.join(missing)}"

        script = composer.compose(ht)
        return f"Composed script for {ht.value}:\n{script}"

    # ------------------------------------------------------------------
    # /hook-stats — dashboard metrics
    # ------------------------------------------------------------------
    async def hook_stats_handler(args: str) -> str:
        """
        Usage: /hook-stats [summary|pass-rate <hook>|failures]
        """
        from lidco.githooks.dashboard import HookDashboard

        parts = shlex.split(args) if args.strip() else []
        # Dashboard is ephemeral in CLI context — show structure
        dash = HookDashboard()

        if not parts or parts[0].lower() == "summary":
            s = dash.summary()
            return (
                f"Total runs: {s['total_runs']}\n"
                f"Pass: {s['total_pass']}  Fail: {s['total_fail']}\n"
                f"Rate: {s['overall_pass_rate']:.1%}\n"
                f"Hooks tracked: {', '.join(s['hooks_tracked']) or '(none)'}"
            )

        subcmd = parts[0].lower()

        if subcmd == "pass-rate":
            if len(parts) < 2:
                return "Error: Usage: /hook-stats pass-rate <hook>"
            rate = dash.pass_rate(parts[1])
            return f"Pass rate for '{parts[1]}': {rate:.1%}"

        if subcmd == "failures":
            failed = dash.most_failed()
            if not failed:
                return "No failures recorded."
            lines = [f"  {f['hook']}: {f['failures']}/{f['total']} failures" for f in failed]
            return "Most failed hooks:\n" + "\n".join(lines)

        return "Unknown subcommand. Try /hook-stats without arguments for help."

    # ------------------------------------------------------------------
    # Register all
    # ------------------------------------------------------------------
    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("git-hooks", "Manage git hooks v2", git_hooks_handler))
    registry.register(SlashCommand("hook-library", "Browse built-in hooks library", hook_library_handler))
    registry.register(SlashCommand("compose-hooks", "Compose multiple hooks into one script", compose_hooks_handler))
    registry.register(SlashCommand("hook-stats", "Hook execution dashboard", hook_stats_handler))
