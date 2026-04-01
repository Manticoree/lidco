"""Adaptive renderer that adjusts output to terminal capabilities."""

from __future__ import annotations

from lidco.terminal.detector import TerminalDetector


_ANSI_COLORS: dict[str, str] = {
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
}


class AdaptiveRenderer:
    """Render text/links/progress adapting to terminal capabilities."""

    def __init__(self, detector: TerminalDetector | None = None) -> None:
        self._detector = detector or TerminalDetector()
        self._caps = self._detector.capabilities()

    def render_text(self, text: str, bold: bool = False, color: str = "") -> str:
        """Render text with optional bold/color ANSI codes if supported."""
        if not self.supports_color():
            return text
        codes: list[str] = []
        if bold:
            codes.append("1")
        if color and color.lower() in _ANSI_COLORS:
            codes.append(_ANSI_COLORS[color.lower()])
        if not codes:
            return text
        prefix = "\033[" + ";".join(codes) + "m"
        return f"{prefix}{text}\033[0m"

    def render_link(self, url: str, label: str = "") -> str:
        """Render an OSC 8 hyperlink if supported, otherwise plain text."""
        display = label or url
        if self._caps.hyperlinks:
            return f"\033]8;;{url}\033\\{display}\033]8;;\033\\"
        return display

    def render_progress(self, fraction: float, width: int = 40) -> str:
        """Render a progress bar using unicode or ASCII."""
        fraction = max(0.0, min(1.0, fraction))
        filled = int(fraction * width)
        if self.supports_unicode():
            bar = "\u2588" * filled + "\u2591" * (width - filled)
        else:
            bar = "#" * filled + "-" * (width - filled)
        pct = int(fraction * 100)
        return f"[{bar}] {pct}%"

    def supports_color(self) -> bool:
        """True if terminal supports at least 256 colors."""
        return self._caps.color_256

    def supports_unicode(self) -> bool:
        """True if terminal supports unicode."""
        return self._caps.unicode

    def fallback_mode(self) -> bool:
        """True if no advanced features are available."""
        return not (
            self._caps.color_256
            or self._caps.truecolor
            or self._caps.unicode
            or self._caps.hyperlinks
            or self._caps.images
            or self._caps.sixel
        )
