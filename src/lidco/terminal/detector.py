"""Terminal type and capability detection."""

from __future__ import annotations

import enum
import os
import sys
from dataclasses import dataclass


class TerminalType(str, enum.Enum):
    """Known terminal emulators."""

    ITERM2 = "iterm2"
    WEZTERM = "wezterm"
    KITTY = "kitty"
    GHOSTTY = "ghostty"
    WINDOWS_TERMINAL = "windows_terminal"
    XTERM = "xterm"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TerminalCapabilities:
    """Feature flags for the detected terminal."""

    color_256: bool = False
    truecolor: bool = False
    unicode: bool = False
    sixel: bool = False
    hyperlinks: bool = False
    images: bool = False


# Capability presets per terminal type.
_CAPABILITIES: dict[TerminalType, TerminalCapabilities] = {
    TerminalType.ITERM2: TerminalCapabilities(
        color_256=True, truecolor=True, unicode=True,
        sixel=True, hyperlinks=True, images=True,
    ),
    TerminalType.WEZTERM: TerminalCapabilities(
        color_256=True, truecolor=True, unicode=True,
        sixel=True, hyperlinks=True, images=True,
    ),
    TerminalType.KITTY: TerminalCapabilities(
        color_256=True, truecolor=True, unicode=True,
        sixel=False, hyperlinks=True, images=True,
    ),
    TerminalType.GHOSTTY: TerminalCapabilities(
        color_256=True, truecolor=True, unicode=True,
        sixel=False, hyperlinks=True, images=False,
    ),
    TerminalType.WINDOWS_TERMINAL: TerminalCapabilities(
        color_256=True, truecolor=True, unicode=True,
        sixel=False, hyperlinks=True, images=False,
    ),
    TerminalType.XTERM: TerminalCapabilities(
        color_256=True, truecolor=False, unicode=True,
        sixel=False, hyperlinks=False, images=False,
    ),
    TerminalType.UNKNOWN: TerminalCapabilities(),
}


class TerminalDetector:
    """Detect terminal type and capabilities from environment."""

    def detect(self) -> TerminalType:
        """Detect the running terminal emulator via env vars."""
        term_program = os.environ.get("TERM_PROGRAM", "").lower()
        if "iterm" in term_program:
            return TerminalType.ITERM2
        if "wezterm" in term_program:
            return TerminalType.WEZTERM

        if os.environ.get("KITTY_WINDOW_ID"):
            return TerminalType.KITTY

        if "ghostty" in term_program:
            return TerminalType.GHOSTTY

        if os.environ.get("WT_SESSION"):
            return TerminalType.WINDOWS_TERMINAL

        term = os.environ.get("TERM", "").lower()
        if "xterm" in term:
            return TerminalType.XTERM

        return TerminalType.UNKNOWN

    def capabilities(self, term_type: TerminalType | None = None) -> TerminalCapabilities:
        """Return capabilities for the given (or detected) terminal type."""
        if term_type is None:
            term_type = self.detect()
        return _CAPABILITIES.get(term_type, TerminalCapabilities())

    def is_interactive(self) -> bool:
        """Return True if stdin is a TTY."""
        return sys.stdin.isatty()

    def terminal_size(self) -> tuple[int, int]:
        """Return (columns, rows)."""
        try:
            size = os.get_terminal_size()
            return (size.columns, size.lines)
        except OSError:
            return (80, 24)

    def summary(self) -> str:
        """Human-readable summary of detected terminal."""
        tt = self.detect()
        caps = self.capabilities(tt)
        parts = [f"Terminal: {tt.value}"]
        features: list[str] = []
        if caps.truecolor:
            features.append("truecolor")
        elif caps.color_256:
            features.append("256-color")
        if caps.unicode:
            features.append("unicode")
        if caps.hyperlinks:
            features.append("hyperlinks")
        if caps.images:
            features.append("images")
        if caps.sixel:
            features.append("sixel")
        if features:
            parts.append("Features: " + ", ".join(features))
        cols, rows = self.terminal_size()
        parts.append(f"Size: {cols}x{rows}")
        return " | ".join(parts)
