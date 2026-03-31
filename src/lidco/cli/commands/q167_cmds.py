"""Q167 CLI commands: /marketplace, /trust."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q167 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /marketplace
    # ------------------------------------------------------------------

    async def marketplace_handler(args: str) -> str:
        from lidco.marketplace.manifest import PluginManifest, TrustLevel
        from lidco.marketplace.discovery import PluginDiscovery
        from lidco.marketplace.installer import PluginInstaller, InstallScope
        from lidco.marketplace.trust_gate import TrustGate

        if "discovery" not in _state:
            _state["discovery"] = PluginDiscovery()
        if "installer" not in _state:
            _state["installer"] = PluginInstaller()
        if "gate" not in _state:
            _state["gate"] = TrustGate()

        discovery: PluginDiscovery = _state["discovery"]  # type: ignore[assignment]
        installer: PluginInstaller = _state["installer"]  # type: ignore[assignment]
        gate: TrustGate = _state["gate"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "search":
            if not rest:
                return "Usage: /marketplace search <query>"
            result = discovery.search(rest)
            if not result.plugins:
                return f"No plugins found for '{rest}'."
            lines = [f"Found {result.total} plugin(s) for '{rest}':"]
            for p in result.plugins:
                lines.append(f"  {p.name} v{p.version} [{p.trust_level.value}] — {p.description}")
            return "\n".join(lines)

        if sub == "browse":
            cat = rest if rest else None
            plugins = discovery.browse(category=cat)
            if not plugins:
                return "No plugins available." if not cat else f"No plugins in category '{cat}'."
            lines = [f"Browsing{' ' + cat if cat else ''} ({len(plugins)} plugins):"]
            for p in plugins:
                lines.append(f"  {p.name} v{p.version} [{p.trust_level.value}] — {p.description}")
            return "\n".join(lines)

        if sub == "info":
            if not rest:
                return "Usage: /marketplace info <name>"
            plugin = discovery.get(rest)
            if plugin is None:
                return f"Plugin '{rest}' not found."
            d = plugin.to_dict()
            return json.dumps(d, indent=2)

        if sub == "install":
            if not rest:
                return "Usage: /marketplace install <name>"
            plugin = discovery.get(rest)
            if plugin is None:
                return f"Plugin '{rest}' not found in marketplace."
            decision = gate.evaluate(plugin)
            if not decision.allowed:
                return f"Install blocked: {decision.reason}"
            installed = installer.install(plugin)
            return f"Installed {plugin.name} v{plugin.version} at {installed.install_path}"

        if sub == "uninstall":
            if not rest:
                return "Usage: /marketplace uninstall <name>"
            removed = installer.uninstall(rest)
            if not removed:
                return f"Plugin '{rest}' is not installed."
            return f"Uninstalled '{rest}'."

        if sub == "list":
            items = installer.list_installed()
            if not items:
                return "No plugins installed."
            lines = [f"{len(items)} installed plugin(s):"]
            for ip in items:
                status = "enabled" if ip.enabled else "disabled"
                lines.append(f"  {ip.manifest.name} v{ip.manifest.version} ({status})")
            return "\n".join(lines)

        return (
            "Usage: /marketplace <subcommand>\n"
            "  search <query>   — search for plugins\n"
            "  browse [cat]     — browse plugins\n"
            "  info <name>      — show plugin details\n"
            "  install <name>   — install a plugin\n"
            "  uninstall <name> — uninstall a plugin\n"
            "  list             — list installed plugins"
        )

    # ------------------------------------------------------------------
    # /trust
    # ------------------------------------------------------------------

    async def trust_handler(args: str) -> str:
        from lidco.marketplace.trust_gate import TrustGate
        from lidco.marketplace.manifest import TrustLevel

        if "gate" not in _state:
            _state["gate"] = TrustGate()

        gate: TrustGate = _state["gate"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "show":
            name = parts[1] if len(parts) > 1 else ""
            if not name:
                return "Usage: /trust show <plugin>"
            return f"Allowed: {gate.is_allowed(name)}"

        if sub == "set":
            name = parts[1] if len(parts) > 1 else ""
            action = parts[2].lower() if len(parts) > 2 else ""
            if not name or not action:
                return "Usage: /trust set <plugin> allow|deny"
            if action == "allow":
                gate.add_to_allowlist(name)
                return f"Added '{name}' to allowlist."
            if action == "deny":
                gate.remove_from_allowlist(name)
                return f"Removed '{name}' from allowlist."
            return f"Unknown action '{action}'. Use 'allow' or 'deny'."

        return (
            "Usage: /trust <subcommand>\n"
            "  show <plugin>            — check plugin trust status\n"
            "  set <plugin> allow|deny  — manage allowlist"
        )

    registry.register(SlashCommand("marketplace", "MCP plugin marketplace", marketplace_handler))
    registry.register(SlashCommand("trust", "Plugin trust management", trust_handler))
