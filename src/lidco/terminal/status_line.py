"""Custom status line display."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatusItem:
    """A single item on the status line."""

    key: str
    value: str
    priority: int = 50


class StatusLine:
    """Manages and renders a status line of key-value items."""

    def __init__(self, width: int = 80) -> None:
        self._width = width
        self._items: dict[str, StatusItem] = {}

    def set(self, key: str, value: str, priority: int = 50) -> None:
        """Set or update an item."""
        self._items[key] = StatusItem(key=key, value=value, priority=priority)

    def remove(self, key: str) -> bool:
        """Remove an item. Return True if it existed."""
        if key in self._items:
            del self._items[key]
            return True
        return False

    def get(self, key: str) -> str | None:
        """Get the value of an item, or None."""
        item = self._items.get(key)
        return item.value if item is not None else None

    def render(self, separator: str = " | ") -> str:
        """Render items sorted by priority (lower first)."""
        sorted_items = sorted(self._items.values(), key=lambda it: it.priority)
        parts = [f"{it.key}: {it.value}" for it in sorted_items]
        return separator.join(parts)

    def clear(self) -> None:
        """Remove all items."""
        self._items = {}

    def item_count(self) -> int:
        """Return number of items."""
        return len(self._items)

    # Convenience setters ------------------------------------------------

    def set_model(self, model: str) -> None:
        """Set the model item."""
        self.set("model", model, priority=10)

    def set_mode(self, mode: str) -> None:
        """Set the mode item."""
        self.set("mode", mode, priority=20)

    def set_tokens(self, used: int, total: int) -> None:
        """Set token usage item."""
        self.set("tokens", f"{used}/{total}", priority=30)
