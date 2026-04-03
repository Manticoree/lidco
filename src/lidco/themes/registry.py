"""ThemeRegistry — Built-in themes; custom theme definition; hot-swap."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field


@dataclass
class Theme:
    """A named visual theme with colors and icons."""

    name: str
    colors: dict[str, str] = field(default_factory=dict)
    icons: dict[str, str] = field(default_factory=dict)
    description: str = ""
    author: str = "system"


_BUILTIN_THEMES: list[Theme] = [
    Theme(
        name="dark",
        colors={
            "bg": "#1e1e1e",
            "fg": "#d4d4d4",
            "accent": "#569cd6",
            "error": "#f44747",
            "warning": "#cca700",
            "success": "#6a9955",
            "info": "#4ec9b0",
            "muted": "#808080",
        },
        icons={"success": "✓", "error": "✗", "warning": "⚠"},
        description="Default dark background theme",
    ),
    Theme(
        name="light",
        colors={
            "bg": "#ffffff",
            "fg": "#333333",
            "accent": "#0066cc",
            "error": "#d32f2f",
            "warning": "#f9a825",
            "success": "#388e3c",
            "info": "#0288d1",
            "muted": "#757575",
        },
        icons={"success": "✓", "error": "✗", "warning": "⚠"},
        description="Light background theme",
    ),
    Theme(
        name="monokai",
        colors={
            "bg": "#272822",
            "fg": "#f8f8f2",
            "accent": "#a6e22e",
            "error": "#f92672",
            "warning": "#e6db74",
            "success": "#a6e22e",
            "info": "#66d9ef",
            "muted": "#75715e",
        },
        icons={"success": "✓", "error": "✗", "warning": "⚠"},
        description="Monokai-inspired color scheme",
    ),
    Theme(
        name="solarized",
        colors={
            "bg": "#002b36",
            "fg": "#839496",
            "accent": "#268bd2",
            "error": "#dc322f",
            "warning": "#b58900",
            "success": "#859900",
            "info": "#2aa198",
            "muted": "#586e75",
        },
        icons={"success": "✓", "error": "✗", "warning": "⚠"},
        description="Solarized dark color scheme",
    ),
    Theme(
        name="dracula",
        colors={
            "bg": "#282a36",
            "fg": "#f8f8f2",
            "accent": "#bd93f9",
            "error": "#ff5555",
            "warning": "#f1fa8c",
            "success": "#50fa7b",
            "info": "#8be9fd",
            "muted": "#6272a4",
        },
        icons={"success": "✓", "error": "✗", "warning": "⚠"},
        description="Dracula color scheme",
    ),
]


class ThemeRegistry:
    """Registry of themes with built-in defaults and hot-swap support."""

    def __init__(self) -> None:
        self._themes: dict[str, Theme] = {}
        self._builtin: set[str] = set()
        self._active_name: str = "dark"
        for t in _BUILTIN_THEMES:
            theme_copy = copy.deepcopy(t)
            self._themes[theme_copy.name] = theme_copy
            self._builtin.add(theme_copy.name)

    def register(self, theme: Theme) -> Theme:
        """Register a custom theme (or overwrite an existing custom one)."""
        self._themes[theme.name] = theme
        return theme

    def get(self, name: str) -> Theme | None:
        """Get a theme by name."""
        return self._themes.get(name)

    def remove(self, name: str) -> bool:
        """Remove a custom theme. Built-in themes cannot be removed."""
        if name in self._builtin:
            return False
        if name in self._themes:
            del self._themes[name]
            if self._active_name == name:
                self._active_name = "dark"
            return True
        return False

    def set_active(self, name: str) -> bool:
        """Set the active theme by name. Returns False if theme not found."""
        if name not in self._themes:
            return False
        self._active_name = name
        return True

    def active(self) -> Theme:
        """Return the currently active theme."""
        return self._themes[self._active_name]

    def all_themes(self) -> list[Theme]:
        """Return all registered themes."""
        return list(self._themes.values())

    def builtin_names(self) -> list[str]:
        """Return names of built-in themes."""
        return sorted(self._builtin)

    def summary(self) -> dict:
        """Return a summary dict of the registry state."""
        return {
            "total": len(self._themes),
            "builtin": len(self._builtin),
            "custom": len(self._themes) - len(self._builtin),
            "active": self._active_name,
            "names": sorted(self._themes.keys()),
        }
