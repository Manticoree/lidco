"""Q168 CLI commands: /cc-import, /cc-compat, /cc-hooks."""
from __future__ import annotations

import json
from typing import Any


def register(registry: Any) -> None:
    """Register Q168 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # -----------------------------------------------------------------
    # /cc-import <path-or-url>
    # -----------------------------------------------------------------
    async def cc_import_handler(args: str) -> str:
        from lidco.compat.cc_manifest import parse_cc_manifest, to_lidco_manifest

        path = args.strip()
        if not path:
            return "Usage: /cc-import <path-or-url>\n  Import a Claude Code plugin manifest."

        # Try to read as local file
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.loads(fh.read())
        except (OSError, json.JSONDecodeError) as exc:
            return f"Failed to read manifest: {exc}"

        try:
            cc_manifest = parse_cc_manifest(data)
        except (TypeError, KeyError) as exc:
            return f"Failed to parse Claude Code manifest: {exc}"

        lidco_manifest = to_lidco_manifest(cc_manifest)
        errors = lidco_manifest.validate()
        if errors:
            return f"Converted manifest has validation errors:\n" + "\n".join(f"  - {e}" for e in errors)

        lines = [
            f"Imported Claude Code plugin: {cc_manifest.name} v{cc_manifest.version}",
            f"  Author: {cc_manifest.author}",
            f"  Description: {cc_manifest.description}",
            f"  Permissions: {', '.join(cc_manifest.permissions) or 'none'}",
            f"  Tools: {len(cc_manifest.tools)}",
            f"  LIDCO trust level: {lidco_manifest.trust_level.value}",
            f"  LIDCO capabilities: {', '.join(c.value for c in lidco_manifest.capabilities) or 'none'}",
        ]
        return "\n".join(lines)

    # -----------------------------------------------------------------
    # /cc-compat [status|scan]
    # -----------------------------------------------------------------
    async def cc_compat_handler(args: str) -> str:
        from lidco.compat.cc_conventions import scan_claude_dir

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "scan"
        path = parts[1].strip() if len(parts) > 1 else "."

        if sub in ("scan", "status"):
            config = scan_claude_dir(path)
            lines = ["Claude Code compatibility scan:"]
            lines.append(f"  Instructions (CLAUDE.md): {'found' if config.instructions else 'not found'}")
            lines.append(f"  Settings: {len(config.settings)} keys")
            lines.append(f"  Custom commands: {len(config.commands)}")
            lines.append(f"  Hooks: {len(config.hooks)}")
            lines.append(f"  MCP servers: {len(config.mcp_servers)}")
            return "\n".join(lines)

        return (
            "Usage: /cc-compat [scan|status] [path]\n"
            "  scan   — scan project for Claude Code conventions\n"
            "  status — show compatibility status"
        )

    # -----------------------------------------------------------------
    # /cc-hooks [list|import]
    # -----------------------------------------------------------------
    async def cc_hooks_handler(args: str) -> str:
        from lidco.compat.cc_hooks import parse_cc_hooks, to_lidco_hooks

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "list"
        path = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            if not path:
                return "Usage: /cc-hooks list <settings-json-path>"
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    settings = json.loads(fh.read())
            except (OSError, json.JSONDecodeError) as exc:
                return f"Failed to read settings: {exc}"

            hooks = parse_cc_hooks(settings)
            if not hooks:
                return "No Claude Code hooks found."
            lines = [f"Found {len(hooks)} Claude Code hook(s):"]
            for h in hooks:
                m = f" (matcher: {h.matcher})" if h.matcher else ""
                lines.append(f"  [{h.event}] {h.command}{m}")
            return "\n".join(lines)

        if sub == "import":
            if not path:
                return "Usage: /cc-hooks import <settings-json-path>"
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    settings = json.loads(fh.read())
            except (OSError, json.JSONDecodeError) as exc:
                return f"Failed to read settings: {exc}"

            hooks = parse_cc_hooks(settings)
            if not hooks:
                return "No Claude Code hooks to import."
            lidco_hooks = to_lidco_hooks(hooks)
            lines = [f"Imported {len(lidco_hooks)} hook(s):"]
            for lh in lidco_hooks:
                lines.append(f"  [{lh['event']}] {lh['command']}")
            return "\n".join(lines)

        return (
            "Usage: /cc-hooks <subcommand> [path]\n"
            "  list <path>   — list Claude Code hooks from settings.json\n"
            "  import <path> — import hooks into LIDCO format"
        )

    registry.register(SlashCommand("cc-import", "Import Claude Code plugin", cc_import_handler))
    registry.register(SlashCommand("cc-compat", "Claude Code compatibility scan", cc_compat_handler))
    registry.register(SlashCommand("cc-hooks", "List/import Claude Code hooks", cc_hooks_handler))
