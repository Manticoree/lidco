"""ColorPalette — Named colors; semantic tokens; 256-color support."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    """An immutable named color with optional semantic token."""

    name: str
    hex: str
    ansi256: int = 0
    semantic: str = ""


_DEFAULT_SEMANTIC_COLORS: list[tuple[str, str, int, str]] = [
    ("red", "#ff0000", 196, "error"),
    ("yellow", "#ffff00", 226, "warning"),
    ("blue", "#0000ff", 21, "info"),
    ("green", "#00ff00", 46, "success"),
    ("gray", "#808080", 244, "muted"),
    ("purple", "#800080", 129, "accent"),
]


class ColorPalette:
    """Named color palette with semantic token support."""

    def __init__(self) -> None:
        self._colors: dict[str, Color] = {}
        for name, hex_val, ansi, sem in _DEFAULT_SEMANTIC_COLORS:
            self._colors[name] = Color(name=name, hex=hex_val, ansi256=ansi, semantic=sem)

    def set(self, name: str, hex: str, ansi256: int = 0, semantic: str = "") -> Color:
        """Add or update a named color."""
        color = Color(name=name, hex=hex, ansi256=ansi256, semantic=semantic)
        self._colors[name] = color
        return color

    def get(self, name: str) -> Color | None:
        """Get a color by name."""
        return self._colors.get(name)

    def get_semantic(self, semantic: str) -> Color | None:
        """Get the first color matching a semantic token."""
        for c in self._colors.values():
            if c.semantic == semantic:
                return c
        return None

    def remove(self, name: str) -> bool:
        """Remove a color by name."""
        if name in self._colors:
            del self._colors[name]
            return True
        return False

    def all_colors(self) -> list[Color]:
        """Return all colors."""
        return list(self._colors.values())

    def by_semantic(self) -> dict[str, Color]:
        """Return a dict mapping semantic tokens to colors."""
        result: dict[str, Color] = {}
        for c in self._colors.values():
            if c.semantic:
                result[c.semantic] = c
        return result

    def to_dict(self) -> dict:
        """Serialize palette to a dict."""
        return {
            name: {
                "hex": c.hex,
                "ansi256": c.ansi256,
                "semantic": c.semantic,
            }
            for name, c in self._colors.items()
        }

    def from_dict(self, data: dict) -> None:
        """Load palette from a dict (adds/overwrites)."""
        for name, info in data.items():
            if isinstance(info, dict):
                self._colors[name] = Color(
                    name=name,
                    hex=info.get("hex", "#000000"),
                    ansi256=info.get("ansi256", 0),
                    semantic=info.get("semantic", ""),
                )

    def summary(self) -> dict:
        """Return a summary dict."""
        semantics = self.by_semantic()
        return {
            "total": len(self._colors),
            "semantic_tokens": sorted(semantics.keys()),
            "names": sorted(self._colors.keys()),
        }
