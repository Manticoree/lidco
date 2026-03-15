"""REPL theme management for LIDCO — Task 433.

Provides 8 built-in themes and support for custom YAML themes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Theme dataclass
# ---------------------------------------------------------------------------

@dataclass
class Theme:
    """A colour theme for the LIDCO REPL.

    Attributes:
        name: Unique theme identifier.
        primary: Primary text/accent colour (Rich markup or hex).
        secondary: Secondary colour.
        accent: Highlight/accent colour.
        background: Background hint (may be ignored in terminal mode).
        error: Error message colour.
        warning: Warning message colour.
        success: Success message colour.
    """

    name: str
    primary: str
    secondary: str
    accent: str
    background: str
    error: str
    warning: str
    success: str


# ---------------------------------------------------------------------------
# Built-in themes
# ---------------------------------------------------------------------------

BUILT_IN_THEMES: dict[str, Theme] = {
    "dark": Theme(
        name="dark",
        primary="bright_white",
        secondary="grey70",
        accent="cyan",
        background="#1e1e1e",
        error="bright_red",
        warning="yellow",
        success="bright_green",
    ),
    "light": Theme(
        name="light",
        primary="black",
        secondary="grey30",
        accent="blue",
        background="#ffffff",
        error="red",
        warning="dark_orange",
        success="green",
    ),
    "solarized": Theme(
        name="solarized",
        primary="#839496",
        secondary="#586e75",
        accent="#268bd2",
        background="#002b36",
        error="#dc322f",
        warning="#b58900",
        success="#859900",
    ),
    "nord": Theme(
        name="nord",
        primary="#d8dee9",
        secondary="#4c566a",
        accent="#88c0d0",
        background="#2e3440",
        error="#bf616a",
        warning="#ebcb8b",
        success="#a3be8c",
    ),
    "monokai": Theme(
        name="monokai",
        primary="#f8f8f2",
        secondary="#75715e",
        accent="#66d9e8",
        background="#272822",
        error="#f92672",
        warning="#e6db74",
        success="#a6e22e",
    ),
    "dracula": Theme(
        name="dracula",
        primary="#f8f8f2",
        secondary="#6272a4",
        accent="#bd93f9",
        background="#282a36",
        error="#ff5555",
        warning="#ffb86c",
        success="#50fa7b",
    ),
    "gruvbox": Theme(
        name="gruvbox",
        primary="#ebdbb2",
        secondary="#928374",
        accent="#83a598",
        background="#282828",
        error="#fb4934",
        warning="#fabd2f",
        success="#b8bb26",
    ),
    "one-dark": Theme(
        name="one-dark",
        primary="#abb2bf",
        secondary="#5c6370",
        accent="#61afef",
        background="#282c34",
        error="#e06c75",
        warning="#e5c07b",
        success="#98c379",
    ),
}


# ---------------------------------------------------------------------------
# ThemeManager
# ---------------------------------------------------------------------------

class ThemeManager:
    """Manage built-in and custom themes.

    Custom themes are loaded from ``~/.lidco/themes/<name>.yaml``.
    """

    _CUSTOM_DIR = Path.home() / ".lidco" / "themes"

    def __init__(self) -> None:
        self._themes: dict[str, Theme] = dict(BUILT_IN_THEMES)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_themes(self) -> list[str]:
        """Return sorted list of available theme names."""
        return sorted(self._themes)

    def load(self, name: str) -> Theme:
        """Load theme by *name*.

        Searches built-ins first, then ``~/.lidco/themes/<name>.yaml``.

        Raises:
            KeyError: If theme is not found.
        """
        if name in self._themes:
            return self._themes[name]
        # Try custom dir
        custom_path = self._CUSTOM_DIR / f"{name}.yaml"
        if custom_path.exists():
            theme = self.load_custom(custom_path)
            self._themes[theme.name] = theme
            return theme
        raise KeyError(f"Theme '{name}' not found. Available: {', '.join(self.list_themes())}")

    def load_custom(self, path: Path) -> Theme:
        """Load a custom theme from a YAML file at *path*.

        YAML must have keys: name, primary, secondary, accent, background,
        error, warning, success.

        Raises:
            ValueError: On missing fields or invalid YAML.
        """
        try:
            import yaml  # type: ignore[import]
        except ImportError:
            # Minimal fallback parser for simple flat YAML
            yaml = None  # type: ignore[assignment]

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Cannot read theme file: {exc}") from exc

        if yaml is not None:
            data: Any = yaml.safe_load(text)
        else:
            data = _parse_simple_yaml(text)

        if not isinstance(data, dict):
            raise ValueError("Theme YAML must be a mapping.")

        required = {"name", "primary", "secondary", "accent", "background", "error", "warning", "success"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"Theme YAML missing fields: {', '.join(sorted(missing))}")

        return Theme(
            name=str(data["name"]),
            primary=str(data["primary"]),
            secondary=str(data["secondary"]),
            accent=str(data["accent"]),
            background=str(data["background"]),
            error=str(data["error"]),
            warning=str(data["warning"]),
            success=str(data["success"]),
        )

    def apply(self, theme: Theme, console: Any) -> None:
        """Apply *theme* to a Rich *console* by setting its style defaults.

        This method is a best-effort helper; if the console does not support
        the operation it is silently skipped.
        """
        try:
            # Rich Console accepts a `style` parameter for default foreground
            if hasattr(console, "style"):
                console.style = theme.primary
        except Exception:
            pass

    def register(self, theme: Theme) -> None:
        """Register a custom theme object."""
        self._themes[theme.name] = theme


# ---------------------------------------------------------------------------
# Minimal YAML parser (fallback when PyYAML is unavailable)
# ---------------------------------------------------------------------------

def _parse_simple_yaml(text: str) -> dict[str, str]:
    """Parse flat key: value YAML (no nesting, no special types)."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result
