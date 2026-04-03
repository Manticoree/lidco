"""ThemeComposer — Compose themes from base + overrides; extend; export/import."""
from __future__ import annotations

import copy
import json

from lidco.themes.registry import Theme, ThemeRegistry


class ThemeComposer:
    """Compose, extend, merge, export, and import themes."""

    def __init__(self, registry: ThemeRegistry) -> None:
        self._registry = registry

    def extend(
        self,
        base_name: str,
        overrides: dict,
        new_name: str,
        description: str = "",
    ) -> Theme:
        """Create a new theme extending a base theme with overrides."""
        base = self._registry.get(base_name)
        if base is None:
            raise ValueError(f"Base theme '{base_name}' not found")
        colors = copy.deepcopy(base.colors)
        icons = copy.deepcopy(base.icons)
        if "colors" in overrides:
            colors.update(overrides["colors"])
        if "icons" in overrides:
            icons.update(overrides["icons"])
        theme = Theme(
            name=new_name,
            colors=colors,
            icons=icons,
            description=description or f"Extended from {base_name}",
            author="user",
        )
        self._registry.register(theme)
        return theme

    def merge(self, theme_a: str, theme_b: str, new_name: str) -> Theme:
        """Merge two themes (b overrides a)."""
        a = self._registry.get(theme_a)
        b = self._registry.get(theme_b)
        if a is None:
            raise ValueError(f"Theme '{theme_a}' not found")
        if b is None:
            raise ValueError(f"Theme '{theme_b}' not found")
        colors = copy.deepcopy(a.colors)
        colors.update(copy.deepcopy(b.colors))
        icons = copy.deepcopy(a.icons)
        icons.update(copy.deepcopy(b.icons))
        theme = Theme(
            name=new_name,
            colors=colors,
            icons=icons,
            description=f"Merged {theme_a} + {theme_b}",
            author="user",
        )
        self._registry.register(theme)
        return theme

    def export_theme(self, name: str) -> str:
        """Export a theme as a JSON string."""
        theme = self._registry.get(name)
        if theme is None:
            raise ValueError(f"Theme '{name}' not found")
        data = {
            "name": theme.name,
            "colors": theme.colors,
            "icons": theme.icons,
            "description": theme.description,
            "author": theme.author,
        }
        return json.dumps(data, indent=2)

    def import_theme(self, json_str: str) -> Theme:
        """Parse a JSON string and register the theme."""
        data = json.loads(json_str)
        theme = Theme(
            name=data["name"],
            colors=data.get("colors", {}),
            icons=data.get("icons", {}),
            description=data.get("description", ""),
            author=data.get("author", "imported"),
        )
        self._registry.register(theme)
        return theme

    def preview(self, name: str) -> str:
        """Return a text preview of a theme's colors and icons."""
        theme = self._registry.get(name)
        if theme is None:
            raise ValueError(f"Theme '{name}' not found")
        lines = [f"Theme: {theme.name}"]
        if theme.description:
            lines.append(f"  {theme.description}")
        if theme.colors:
            lines.append("Colors:")
            for k, v in sorted(theme.colors.items()):
                lines.append(f"  {k}: {v}")
        if theme.icons:
            lines.append("Icons:")
            for k, v in sorted(theme.icons.items()):
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def summary(self) -> dict:
        """Return a summary dict."""
        return {
            "registry_themes": len(self._registry.all_themes()),
        }
