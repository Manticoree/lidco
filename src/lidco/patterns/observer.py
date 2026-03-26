"""Observer pattern — Observable mixin, ObservableValue, ObservableList (stdlib)."""
from __future__ import annotations

from typing import Any, Callable, Iterator


class Observable:
    """Mixin that provides observer registration and notification."""

    def __init__(self) -> None:
        self._observers: dict[str, Callable[..., None]] = {}

    def add_observer(self, name: str, fn: Callable[..., None]) -> None:
        """Register *fn* under *name*."""
        self._observers = {**self._observers, name: fn}

    def remove_observer(self, name: str) -> bool:
        """Remove observer by name.  Return True if it existed."""
        if name not in self._observers:
            return False
        self._observers = {k: v for k, v in self._observers.items() if k != name}
        return True

    def notify(self, event: str, **kwargs: Any) -> int:
        """
        Call all observers with *event* and *kwargs*.
        Exceptions in observers are swallowed.
        Return count of observers notified.
        """
        count = 0
        for fn in list(self._observers.values()):
            try:
                fn(event, **kwargs)
            except Exception:  # noqa: BLE001
                pass
            count += 1
        return count

    @property
    def observer_count(self) -> int:
        return len(self._observers)


class ObservableValue(Observable):
    """An observable single value that notifies on change."""

    def __init__(self, initial: Any = None) -> None:
        super().__init__()
        self._value = initial

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, new: Any) -> None:
        if new != self._value:
            old = self._value
            self._value = new
            self.notify("change", old=old, new=new)


class ObservableList(Observable):
    """A list-like container that notifies on mutation."""

    def __init__(self, initial: list | None = None) -> None:
        super().__init__()
        self._items: list = list(initial) if initial else []

    @property
    def items(self) -> list:
        """Return a shallow copy of the internal list."""
        return list(self._items)

    def append(self, item: Any) -> None:
        self._items.append(item)
        self.notify("append", item=item, index=len(self._items) - 1)

    def remove(self, item: Any) -> None:
        """Remove first occurrence of *item*.  Raises ValueError if missing."""
        self._items.remove(item)  # raises ValueError if not found
        self.notify("remove", item=item)

    def clear(self) -> None:
        count = len(self._items)
        self._items = []
        self.notify("clear", count=count)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> Any:
        return self._items[index]

    def __iter__(self) -> Iterator:
        return iter(self._items)

    def __contains__(self, item: Any) -> bool:
        return item in self._items
