"""Screen controller for simulated mouse/keyboard operations."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Coordinate:
    """An (x, y) screen coordinate."""

    x: int
    y: int


class ScreenController:
    """Simulated screen controller tracking cursor state and action history."""

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self._width = width
        self._height = height
        self._cursor = Coordinate(0, 0)
        self._history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _clamp(self, x: int, y: int) -> Coordinate:
        cx = max(0, min(x, self._width - 1))
        cy = max(0, min(y, self._height - 1))
        return Coordinate(cx, cy)

    def _record(self, action: str, **kwargs: Any) -> None:
        self._history.append({"action": action, "timestamp": time.time(), **kwargs})

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def move(self, x: int, y: int) -> Coordinate:
        """Move cursor to *(x, y)* and return the new position."""
        pos = self._clamp(x, y)
        self._cursor = pos
        self._record("move", x=pos.x, y=pos.y)
        return pos

    def click(self, x: int, y: int, button: str = "left") -> Coordinate:
        """Simulate a click at *(x, y)*."""
        pos = self.move(x, y)
        self._record("click", x=pos.x, y=pos.y, button=button)
        return pos

    def double_click(self, x: int, y: int) -> Coordinate:
        """Simulate a double-click at *(x, y)*."""
        pos = self.move(x, y)
        self._record("double_click", x=pos.x, y=pos.y)
        return pos

    def drag(
        self, from_x: int, from_y: int, to_x: int, to_y: int
    ) -> tuple[Coordinate, Coordinate]:
        """Simulate a drag from one point to another."""
        start = self._clamp(from_x, from_y)
        end = self._clamp(to_x, to_y)
        self._cursor = end
        self._record("drag", from_x=start.x, from_y=start.y, to_x=end.x, to_y=end.y)
        return start, end

    def type_text(self, text: str) -> str:
        """Simulate typing *text*; return the text typed."""
        self._record("type_text", text=text)
        return text

    def hotkey(self, *keys: str) -> str:
        """Simulate a hotkey combo; return the combo string."""
        combo = "+".join(keys)
        self._record("hotkey", keys=combo)
        return combo

    def cursor_position(self) -> Coordinate:
        """Return current cursor position."""
        return self._cursor

    def screen_size(self) -> tuple[int, int]:
        """Return *(width, height)* of the screen."""
        return self._width, self._height

    def action_history(self) -> list[dict[str, Any]]:
        """Return list of all recorded actions."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear the action history."""
        self._history.clear()
