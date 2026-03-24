"""CLI commands for Q92: /prompt /export /team /hot-reload."""

from __future__ import annotations


def register_q92_commands(registry) -> None:  # noqa: ANN001
    """Register Q92 slash commands into *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /prompt
    # ------------------------------------------------------------------
    def prompt_handler(args: str) -> str:
        """Handle /prompt list | run <name> [key=val ...] | save <name> <content>."""
        from lidco.prompts.library import PromptTemplateLibrary

        lib = PromptTemplateLibrary()
        parts = args.strip().split(None, 1)
        subcmd = parts[0].lower() if parts else "list"
        rest = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            templates = lib.list()
            if not templates:
                return "No prompt templates found. Add *.md files to .lidco/prompts/"
            lines = ["Available prompt templates:"]
            for tpl in templates:
                var_hint = f"  vars: {', '.join(tpl.variables)}" if tpl.variables else ""
                lines.append(f"  {tpl.name}{var_hint}")
            return "\n".join(lines)

        if subcmd == "run":
            run_parts = rest.split(None, 1)
            name = run_parts[0] if run_parts else ""
            if not name:
                return "Usage: /prompt run <name> [key=val ...]"
            var_str = run_parts[1] if len(run_parts) > 1 else ""
            variables: dict[str, str] = {}
            for token in var_str.split():
                if "=" in token:
                    k, _, v = token.partition("=")
                    variables[k] = v
            result = lib.render(name, variables)
            if not result.found:
                return f"Template '{name}' not found."
            lines = [result.rendered]
            if result.missing_vars:
                lines.append(
                    f"\n[warning: missing variables: {', '.join(result.missing_vars)}]"
                )
            return "\n".join(lines)

        if subcmd == "save":
            save_parts = rest.split(None, 1)
            if len(save_parts) < 2:
                return "Usage: /prompt save <name> <content>"
            name, content = save_parts[0], save_parts[1]
            tpl = lib.save(name, content)
            return f"Saved prompt template '{tpl.name}' to {tpl.source_path}"

        return "Usage: /prompt [list | run <name> [key=val ...] | save <name> <content>]"

    registry.register(SlashCommand("prompt", "Manage prompt templates", prompt_handler))

    # ------------------------------------------------------------------
    # /export
    # ------------------------------------------------------------------
    def export_handler(args: str) -> str:
        """Handle /export [html|md] [output_path]."""
        from lidco.export.session_exporter import ExportConfig, SessionExporter

        parts = args.strip().split()
        fmt = "markdown"
        out_path: str | None = None

        for part in parts:
            if part.lower() in ("html", "md", "markdown"):
                fmt = "html" if part.lower() == "html" else "markdown"
            else:
                out_path = part

        messages = getattr(registry, "_last_messages", [])
        if not messages:
            return "No conversation messages to export."

        exporter = SessionExporter()
        config = ExportConfig(format=fmt)
        result = exporter.export(messages, config)

        if out_path:
            saved = exporter.save(result, out_path)
            return f"Exported {result.message_count} messages ({fmt}) → {saved}"

        # Return inline preview (first 1500 chars)
        preview = result.content[:1500]
        if len(result.content) > 1500:
            preview += "\n... [truncated — use /export <format> <path> to save full output]"
        return preview

    registry.register(SlashCommand("export", "Export session to HTML or Markdown", export_handler))

    # ------------------------------------------------------------------
    # /team
    # ------------------------------------------------------------------
    def team_handler(args: str) -> str:
        """Handle /team show | validate."""
        from lidco.config.team_config import TeamConfigLoader

        loader = TeamConfigLoader()
        subcmd = args.strip().lower() or "show"

        if subcmd == "show":
            merged = loader.load()
            r = merged.resolved
            lines = ["Team configuration:"]
            lines.append(f"  model:       {r.get('model') or '(not set)'}")
            tools = r.get("tools", [])
            lines.append(f"  tools:       {', '.join(tools) if tools else '(none)'}")
            rules = r.get("rules", [])
            lines.append(f"  rules:       {len(rules)} rule(s)")
            members = r.get("members", [])
            lines.append(f"  members:     {', '.join(members) if members else '(none)'}")
            perms = r.get("permissions", {})
            if perms:
                lines.append(f"  permissions: {perms}")
            if merged.personal:
                lines.append("  (personal overrides applied)")
            return "\n".join(lines)

        if subcmd == "validate":
            team = loader.load_team()
            if team is None:
                return "No .lidco/team.yaml found."
            errors = loader.validate(team)
            if not errors:
                return "team.yaml is valid."
            return "Validation errors:\n" + "\n".join(f"  - {e}" for e in errors)

        return "Usage: /team [show | validate]"

    registry.register(SlashCommand("team", "Show or validate team configuration", team_handler))

    # ------------------------------------------------------------------
    # /hot-reload
    # ------------------------------------------------------------------
    def hot_reload_handler(args: str) -> str:
        """Reload LidcoConfig from disk without restarting the REPL."""
        try:
            from lidco.core.config import load_config

            config = load_config()
            return f"Configuration reloaded. Model: {getattr(config, 'model', '(default)')}"
        except Exception as exc:  # noqa: BLE001
            return f"Hot-reload failed: {exc}"

    registry.register(
        SlashCommand("hot-reload", "Reload configuration from disk", hot_reload_handler)
    )
