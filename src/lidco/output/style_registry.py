"""Output style registry — task 1072.

Defines the OutputStyle protocol and StyleRegistry for managing
named output transformation styles with immutable state.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OutputStyle(Protocol):
    """Protocol for output styles that transform text."""

    @property
    def name(self) -> str: ...

    def transform(self, text: str) -> str: ...

    def wrap_response(self, response: str) -> str: ...


class DefaultStyle:
    """Pass-through style — no transformation."""

    @property
    def name(self) -> str:
        return "default"

    def transform(self, text: str) -> str:
        return text

    def wrap_response(self, response: str) -> str:
        return response


class BriefStyle:
    """Concise style — strips blank lines and limits output."""

    @property
    def name(self) -> str:
        return "brief"

    def transform(self, text: str) -> str:
        lines = [line for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def wrap_response(self, response: str) -> str:
        lines = [line for line in response.splitlines() if line.strip()]
        if len(lines) > 10:
            lines = lines[:10]
            lines.append("... (truncated)")
        return "\n".join(lines)


class StyleRegistry:
    """Immutable registry of named output styles."""

    def __init__(
        self,
        styles: tuple[OutputStyle, ...] = (),
        active_name: str | None = None,
    ) -> None:
        self._styles = {s.name: s for s in styles}
        self._active_name = active_name

    def register(self, style: OutputStyle) -> StyleRegistry:
        """Return a new registry with *style* added."""
        existing = tuple(
            s for s in self._styles.values() if s.name != style.name
        )
        return StyleRegistry((*existing, style), self._active_name)

    def get(self, name: str) -> OutputStyle | None:
        """Return the style with *name*, or ``None``."""
        return self._styles.get(name)

    def list_styles(self) -> tuple[str, ...]:
        """Return a sorted tuple of registered style names."""
        return tuple(sorted(self._styles.keys()))

    @property
    def active(self) -> OutputStyle | None:
        """Return the currently active style, or ``None``."""
        if self._active_name is None:
            return None
        return self._styles.get(self._active_name)

    def set_active(self, name: str) -> StyleRegistry:
        """Return a new registry with *name* as the active style.

        Raises ``KeyError`` if *name* is not registered.
        """
        if name not in self._styles:
            raise KeyError(f"Unknown style: {name!r}")
        return StyleRegistry(tuple(self._styles.values()), name)
