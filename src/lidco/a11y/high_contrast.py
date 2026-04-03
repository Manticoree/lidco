"""High contrast color scheme; configurable contrast ratio; WCAG compliance."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContrastPair:
    """Result of a contrast check between two colours."""

    foreground: str
    background: str
    ratio: float
    passes_aa: bool
    passes_aaa: bool


class HighContrastMode:
    """High-contrast mode with WCAG contrast checking."""

    _PALETTE: dict[str, str] = {
        "text": "#FFFFFF",
        "background": "#000000",
        "link": "#FFFF00",
        "error": "#FF0000",
        "success": "#00FF00",
        "warning": "#FFA500",
        "info": "#00FFFF",
        "border": "#FFFFFF",
    }

    def __init__(self, enabled: bool = False, min_ratio: float = 4.5) -> None:
        self._enabled = enabled
        self._min_ratio = min_ratio

    # -- enable / disable -----------------------------------------------------

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    # -- contrast calculations -----------------------------------------------

    @staticmethod
    def _luminance(hex_color: str) -> float:
        """Relative luminance per WCAG 2.1."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255

        def _lin(c: float) -> float:
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)

    @staticmethod
    def _contrast_ratio(l1: float, l2: float) -> float:
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    def check_contrast(self, fg_hex: str, bg_hex: str) -> ContrastPair:
        l_fg = self._luminance(fg_hex)
        l_bg = self._luminance(bg_hex)
        ratio = self._contrast_ratio(l_fg, l_bg)
        ratio = round(ratio, 2)
        return ContrastPair(
            foreground=fg_hex,
            background=bg_hex,
            ratio=ratio,
            passes_aa=ratio >= 4.5,
            passes_aaa=ratio >= 7.0,
        )

    def suggest_fix(self, fg_hex: str, bg_hex: str) -> str:
        """Suggest a higher-contrast foreground colour."""
        pair = self.check_contrast(fg_hex, bg_hex)
        if pair.passes_aa:
            return fg_hex
        l_bg = self._luminance(bg_hex)
        # If background is dark, suggest white; otherwise suggest black.
        if l_bg < 0.5:
            return "#FFFFFF"
        return "#000000"

    def palette(self) -> dict[str, str]:
        return dict(self._PALETTE)

    # -- summary --------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "enabled": self._enabled,
            "min_ratio": self._min_ratio,
            "palette_size": len(self._PALETTE),
        }
