"""Flicker-free rendering with virtual scrollback."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class RenderMode(str, enum.Enum):
    """Render output mode."""

    NORMAL = "normal"
    ALT_SCREEN = "alt_screen"
    MINIMAL = "minimal"


@dataclass
class RenderBuffer:
    """Virtual screen buffer."""

    lines: list[str] = field(default_factory=list)
    width: int = 80
    height: int = 24
    dirty: bool = True

    def write(self, line: str) -> None:
        """Append a line to the buffer."""
        self.lines.append(line)
        self.dirty = True

    def clear(self) -> None:
        """Clear all lines."""
        self.lines = []
        self.dirty = True

    def render(self) -> str:
        """Join lines with newlines."""
        return "\n".join(self.lines)

    def diff(self, other: "RenderBuffer") -> list[int]:
        """Return indices of lines that differ between self and *other*."""
        changed: list[int] = []
        max_len = max(len(self.lines), len(other.lines))
        for i in range(max_len):
            a = self.lines[i] if i < len(self.lines) else None
            b = other.lines[i] if i < len(other.lines) else None
            if a != b:
                changed.append(i)
        return changed


class RenderEngine:
    """Flicker-free terminal render engine."""

    def __init__(
        self,
        mode: RenderMode = RenderMode.NORMAL,
        width: int = 80,
        height: int = 24,
    ) -> None:
        self._mode = mode
        self._buffer = RenderBuffer(width=width, height=height)

    def write(self, content: str) -> None:
        """Write content lines to the buffer."""
        for line in content.splitlines():
            self._buffer.write(line)

    def flush(self) -> str:
        """Return rendered output and mark buffer clean."""
        output = self._buffer.render()
        self._buffer.dirty = False
        return output

    def set_mode(self, mode: RenderMode) -> None:
        """Change the render mode."""
        self._mode = mode

    def resize(self, width: int, height: int) -> None:
        """Resize the virtual buffer."""
        self._buffer.width = width
        self._buffer.height = height
        self._buffer.dirty = True

    def clear(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()

    def line_count(self) -> int:
        """Return the number of lines in the buffer."""
        return len(self._buffer.lines)

    @property
    def buffer(self) -> RenderBuffer:
        """Access the underlying buffer."""
        return self._buffer
