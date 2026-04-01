"""Q183 CLI commands: /sdk, /extensions, /plugin-lifecycle, /tool-builder."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q183 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /sdk
    # ------------------------------------------------------------------

    async def sdk_handler(args: str) -> str:
        from lidco.sdk.extension_points import ExtensionPointRegistry

        reg = ExtensionPointRegistry()
        lines = [
            "LIDCO Plugin SDK",
            "=================",
            "",
            "Components:",
            "  - ExtensionPointRegistry: define and invoke extension points",
            "  - PluginLifecycleManager: manage plugin lifecycle (register -> init -> activate -> deactivate -> uninstall)",
            "  - ToolBuilder: fluent API for creating custom tools",
            "  - PluginScaffoldGenerator: generate plugin project scaffolds",
            "",
            f"Extension points defined: {reg.point_count()}",
            f"Total hooks registered: {reg.hook_count()}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /extensions
    # ------------------------------------------------------------------

    async def extensions_handler(args: str) -> str:
        from lidco.sdk.extension_points import ExtensionPointRegistry

        reg = ExtensionPointRegistry()
        points = reg.list_points()
        if not points:
            return "No extension points defined."
        lines = [f"{len(points)} extension point(s):"]
        for pt in points:
            hook_count = reg.hook_count(pt.name)
            lines.append(f"  {pt.name} — {pt.description or '(no description)'} [{hook_count} hook(s)]")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /plugin-lifecycle
    # ------------------------------------------------------------------

    async def plugin_lifecycle_handler(args: str) -> str:
        from lidco.sdk.lifecycle import PluginLifecycleManager

        mgr = PluginLifecycleManager()
        plugins = mgr.list_plugins()
        if not plugins:
            return "No managed plugins."
        lines = [f"{len(plugins)} managed plugin(s):"]
        for p in plugins:
            lines.append(f"  {p.name} v{p.version} [{p.state.value}]")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /tool-builder
    # ------------------------------------------------------------------

    async def tool_builder_handler(args: str) -> str:
        lines = [
            "ToolBuilder — Fluent API for creating custom tools",
            "",
            "Usage:",
            "  from lidco.sdk.tool_builder import ToolBuilder",
            "",
            "  tool = (",
            '      ToolBuilder("my_tool")',
            '      .description("Does something")',
            '      .add_param("input", "string", "The input")',
            "      .handler(my_handler)",
            "      .build()",
            "  )",
            "",
            "Methods: description(), add_param(), set_permission(), handler(),",
            "         set_metadata(), validate(), build(), build_and_register(),",
            "         get_spec(), reset()",
        ]
        return "\n".join(lines)

    registry.register(SlashCommand("sdk", "Show SDK info and extension points summary", sdk_handler))
    registry.register(SlashCommand("extensions", "List extension points", extensions_handler))
    registry.register(SlashCommand("plugin-lifecycle", "List managed plugins", plugin_lifecycle_handler))
    registry.register(SlashCommand("tool-builder", "Show tool builder help", tool_builder_handler))
