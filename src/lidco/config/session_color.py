"""SessionColorManager — store and retrieve terminal session color.

Task 730: Q119.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional


class ColorError(ValueError):
    """Raised for invalid color names or values."""


NAMED_COLORS: dict[str, str] = {
    "default": "\033[39m",
    "reset": "\033[0m",
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_black": "\033[90m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
    "bright_white": "\033[97m",
}

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class SessionColorManager:
    """Persist and retrieve the active session color."""

    def __init__(
        self,
        store_path: str = "/tmp/session_color.json",
        write_fn: Optional[Callable[[str, str], None]] = None,
        read_fn: Optional[Callable[[str], str]] = None,
    ) -> None:
        self._store_path = store_path
        self._write_fn = write_fn or self._default_write
        self._read_fn = read_fn or self._default_read
        self._color: Optional[str] = None

    def get_color(self) -> Optional[str]:
        return self._color

    def set_color(self, color: str) -> str:
        """Set color (named or hex). Raises ColorError on invalid input."""
        if not self._is_valid(color):
            raise ColorError(f"Unknown color: {color!r}")
        self._color = color
        self._persist()
        return color

    def clear_color(self) -> None:
        self._color = None
        self._persist()

    def reset(self) -> None:
        """Alias for clear_color."""
        self.clear_color()

    def get_ansi_prefix(self) -> str:
        """Return ANSI escape for the current color, or '' for hex/unset."""
        if self._color is None:
            return ""
        return NAMED_COLORS.get(self._color, "")

    def list_colors(self) -> list[str]:
        """Return sorted list of named colors."""
        return sorted(NAMED_COLORS.keys())

    def load(self) -> None:
        try:
            raw = self._read_fn(self._store_path)
            data = json.loads(raw)
            color = data.get("color")
            if color and self._is_valid(color):
                self._color = color
        except Exception:
            pass

    # ------------------------------------------------------------------ #

    def _is_valid(self, color: str) -> bool:
        if color in NAMED_COLORS:
            return True
        if _HEX_RE.match(color):
            return True
        return False

    def _persist(self) -> None:
        data = json.dumps({"color": self._color})
        self._write_fn(self._store_path, data)

    @staticmethod
    def _default_write(path: str, data: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data)

    @staticmethod
    def _default_read(path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
