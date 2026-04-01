"""Q184 CLI commands: /marketplace2, /marketplace2-search, /marketplace2-install, /marketplace2-uninstall."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q184 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /marketplace2
    # ------------------------------------------------------------------

    async def marketplace2_handler(args: str) -> str:
        from lidco.marketplace.manifest2 import (
            MarketplaceIndex,
            PluginCategory,
            PluginManifest2,
        )
        from lidco.marketplace.registry2 import MarketplaceRegistry

        if "registry" not in _state:
            _state["registry"] = MarketplaceRegistry()
        reg: MarketplaceRegistry = _state["registry"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            plugins = reg.list_all()
            if not plugins:
                return "No plugins registered in marketplace."
            lines = [f"{len(plugins)} plugin(s) in marketplace:"]
            for p in plugins:
                lines.append(
                    f"  {p.name} v{p.version} [{p.category.value}] — {p.description}"
                )
            return "\n".join(lines)

        if sub == "info":
            if not rest:
                return "Usage: /marketplace2 info <name>"
            plugin = reg.get(rest)
            if plugin is None:
                return f"Plugin '{rest}' not found."
            return json.dumps(plugin.to_dict(), indent=2)

        if sub == "categories":
            cats = reg.categories()
            if not cats:
                return "No categories available."
            lines = ["Categories:"]
            for cat, plugins in sorted(cats.items()):
                lines.append(f"  {cat}: {len(plugins)} plugin(s)")
            return "\n".join(lines)

        return (
            "Usage: /marketplace2 <subcommand>\n"
            "  list             — list all plugins\n"
            "  info <name>      — show plugin details\n"
            "  categories       — show category counts"
        )

    # ------------------------------------------------------------------
    # /marketplace2-search
    # ------------------------------------------------------------------

    async def marketplace2_search_handler(args: str) -> str:
        from lidco.marketplace.manifest2 import PluginCategory
        from lidco.marketplace.registry2 import MarketplaceRegistry

        if "registry" not in _state:
            _state["registry"] = MarketplaceRegistry()
        reg: MarketplaceRegistry = _state["registry"]  # type: ignore[assignment]

        query = args.strip()
        if not query:
            return "Usage: /marketplace2-search <query>"

        results = reg.search(query)
        if not results:
            return f"No plugins found for '{query}'."
        lines = [f"Found {len(results)} plugin(s) for '{query}':"]
        for p in results:
            lines.append(
                f"  {p.name} v{p.version} [{p.category.value}] — {p.description}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /marketplace2-install
    # ------------------------------------------------------------------

    async def marketplace2_install_handler(args: str) -> str:
        from lidco.marketplace.installer2 import PluginInstaller2
        from lidco.marketplace.registry2 import MarketplaceRegistry

        if "registry" not in _state:
            _state["registry"] = MarketplaceRegistry()
        if "installer" not in _state:
            _state["installer"] = PluginInstaller2()
        reg: MarketplaceRegistry = _state["registry"]  # type: ignore[assignment]
        installer: PluginInstaller2 = _state["installer"]  # type: ignore[assignment]

        name = args.strip()
        if not name:
            return "Usage: /marketplace2-install <plugin-name>"

        manifest = reg.get(name)
        if manifest is None:
            return f"Plugin '{name}' not found in marketplace."

        if installer.is_installed(name):
            return f"Plugin '{name}' is already installed."

        installed = installer.install(manifest)
        return f"Installed {installed.name} v{installed.version} at {installed.path}"

    # ------------------------------------------------------------------
    # /marketplace2-uninstall
    # ------------------------------------------------------------------

    async def marketplace2_uninstall_handler(args: str) -> str:
        from lidco.marketplace.installer2 import PluginInstaller2

        if "installer" not in _state:
            _state["installer"] = PluginInstaller2()
        installer: PluginInstaller2 = _state["installer"]  # type: ignore[assignment]

        name = args.strip()
        if not name:
            return "Usage: /marketplace2-uninstall <plugin-name>"

        removed = installer.uninstall(name)
        if not removed:
            return f"Plugin '{name}' is not installed."
        return f"Uninstalled '{name}'."

    registry.register(SlashCommand("marketplace2", "Plugin marketplace v2", marketplace2_handler))
    registry.register(SlashCommand("marketplace2-search", "Search plugin marketplace", marketplace2_search_handler))
    registry.register(SlashCommand("marketplace2-install", "Install marketplace plugin", marketplace2_install_handler))
    registry.register(SlashCommand("marketplace2-uninstall", "Uninstall marketplace plugin", marketplace2_uninstall_handler))
