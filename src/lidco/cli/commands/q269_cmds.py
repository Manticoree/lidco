"""
Q269 CLI commands — /theme, /colors, /icons, /theme-export

Registered via register_q269_commands(registry).
"""
from __future__ import annotations

import json
import shlex


def register_q269_commands(registry) -> None:
    """Register Q269 slash commands onto the given registry."""

    # Shared state for the session
    _state: dict[str, object] = {}

    def _get_registry():
        from lidco.themes.registry import ThemeRegistry

        if "registry" not in _state:
            _state["registry"] = ThemeRegistry()
        return _state["registry"]

    def _get_composer():
        from lidco.themes.composer import ThemeComposer

        if "composer" not in _state:
            _state["composer"] = ThemeComposer(_get_registry())
        return _state["composer"]

    def _get_palette():
        from lidco.themes.palette import ColorPalette

        if "palette" not in _state:
            _state["palette"] = ColorPalette()
        return _state["palette"]

    def _get_iconset():
        from lidco.themes.icons import IconSet

        if "iconset" not in _state:
            _state["iconset"] = IconSet()
        return _state["iconset"]

    # ------------------------------------------------------------------
    # /theme — Theme management
    # ------------------------------------------------------------------
    async def theme_handler(args: str) -> str:
        """
        Usage: /theme list
               /theme set <name>
               /theme info <name>
               /theme create <name> <json_colors>
        """
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /theme <subcommand>\n"
                "  list              list all themes\n"
                "  set <name>        set active theme\n"
                "  info <name>       show theme details\n"
                "  create <name> <json_colors>  create custom theme"
            )

        reg = _get_registry()
        subcmd = parts[0].lower()

        if subcmd == "list":
            themes = reg.all_themes()
            if not themes:
                return "No themes registered."
            lines = []
            active = reg.active()
            for t in themes:
                marker = " *" if t.name == active.name else ""
                lines.append(f"  {t.name}{marker} — {t.description}")
            return "Themes:\n" + "\n".join(lines)

        if subcmd == "set":
            if len(parts) < 2:
                return "Error: name required. Usage: /theme set <name>"
            ok = reg.set_active(parts[1])
            if ok:
                return f"Active theme set to '{parts[1]}'."
            return f"Theme '{parts[1]}' not found."

        if subcmd == "info":
            if len(parts) < 2:
                return "Error: name required. Usage: /theme info <name>"
            composer = _get_composer()
            try:
                return composer.preview(parts[1])
            except ValueError as exc:
                return f"Error: {exc}"

        if subcmd == "create":
            if len(parts) < 3:
                return "Error: Usage: /theme create <name> <json_colors>"
            name = parts[1]
            try:
                colors = json.loads(parts[2])
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"
            from lidco.themes.registry import Theme

            theme = Theme(name=name, colors=colors, author="user")
            reg.register(theme)
            return f"Theme '{name}' created with {len(colors)} color(s)."

        return f"Unknown subcommand '{subcmd}'. Use list/set/info/create."

    registry.register_async("theme", "Theme management — list, set, info, create", theme_handler)

    # ------------------------------------------------------------------
    # /colors — Color palette management
    # ------------------------------------------------------------------
    async def colors_handler(args: str) -> str:
        """
        Usage: /colors list
               /colors set <name> <hex>
               /colors semantic <token>
        """
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /colors <subcommand>\n"
                "  list              list all palette colors\n"
                "  set <name> <hex>  set a named color\n"
                "  semantic <token>  lookup by semantic token"
            )

        palette = _get_palette()
        subcmd = parts[0].lower()

        if subcmd == "list":
            colors = palette.all_colors()
            if not colors:
                return "No colors defined."
            lines = [f"  {c.name}: {c.hex} (semantic={c.semantic or 'none'})" for c in colors]
            return "Colors:\n" + "\n".join(lines)

        if subcmd == "set":
            if len(parts) < 3:
                return "Error: Usage: /colors set <name> <hex>"
            c = palette.set(parts[1], parts[2])
            return f"Color '{c.name}' set to {c.hex}."

        if subcmd == "semantic":
            if len(parts) < 2:
                return "Error: Usage: /colors semantic <token>"
            c = palette.get_semantic(parts[1])
            if c is None:
                return f"No color with semantic token '{parts[1]}'."
            return f"{c.name}: {c.hex} (semantic={c.semantic})"

        return f"Unknown subcommand '{subcmd}'. Use list/set/semantic."

    registry.register_async("colors", "Color palette management", colors_handler)

    # ------------------------------------------------------------------
    # /icons — Icon management
    # ------------------------------------------------------------------
    async def icons_handler(args: str) -> str:
        """
        Usage: /icons list
               /icons set <name> <unicode> <ascii>
               /icons toggle-unicode
        """
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /icons <subcommand>\n"
                "  list                          list all icons\n"
                "  set <name> <unicode> <ascii>  set an icon\n"
                "  toggle-unicode                toggle unicode/ascii mode"
            )

        iconset = _get_iconset()
        subcmd = parts[0].lower()

        if subcmd == "list":
            icons = iconset.all_icons()
            if not icons:
                return "No icons defined."
            lines = [f"  {i.name}: {iconset.get(i.name)} ({i.category})" for i in icons]
            return "Icons:\n" + "\n".join(lines)

        if subcmd == "set":
            if len(parts) < 4:
                return "Error: Usage: /icons set <name> <unicode> <ascii>"
            icon = iconset.set(parts[1], parts[2], parts[3])
            return f"Icon '{icon.name}' set."

        if subcmd == "toggle-unicode":
            # Flip the current state
            current = iconset._use_unicode
            iconset.toggle_unicode(not current)
            mode = "unicode" if not current else "ASCII"
            return f"Icon mode toggled to {mode}."

        return f"Unknown subcommand '{subcmd}'. Use list/set/toggle-unicode."

    registry.register_async("icons", "Icon set management", icons_handler)

    # ------------------------------------------------------------------
    # /theme-export — Export/import themes
    # ------------------------------------------------------------------
    async def theme_export_handler(args: str) -> str:
        """
        Usage: /theme-export export <name>
               /theme-export import <json>
        """
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /theme-export <subcommand>\n"
                "  export <name>  export theme as JSON\n"
                "  import <json>  import theme from JSON"
            )

        composer = _get_composer()
        subcmd = parts[0].lower()

        if subcmd == "export":
            if len(parts) < 2:
                return "Error: Usage: /theme-export export <name>"
            try:
                return composer.export_theme(parts[1])
            except ValueError as exc:
                return f"Error: {exc}"

        if subcmd == "import":
            if len(parts) < 2:
                return "Error: Usage: /theme-export import <json>"
            json_str = parts[1]
            try:
                theme = composer.import_theme(json_str)
            except (json.JSONDecodeError, KeyError) as exc:
                return f"Error: invalid theme JSON — {exc}"
            return f"Theme '{theme.name}' imported."

        return f"Unknown subcommand '{subcmd}'. Use export/import."

    registry.register_async("theme-export", "Export and import themes as JSON", theme_export_handler)
