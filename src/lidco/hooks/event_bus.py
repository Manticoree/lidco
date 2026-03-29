"""HookEventBus — pub/sub event bus for hook events (Task 717)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class HookEvent:
    """A hook event with type, payload, timestamp and unique id."""

    event_type: str
    payload: dict
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: "%x" % id(object()) + "-%x" % int(time.time() * 1e9))


class HookEventBus:
    """Pub/sub event bus for hook events.

    Subscriber lists use immutable replacement (copy-on-write) for thread safety.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Add handler for *event_type*. ``'*'`` matches all events."""
        current = self._subscribers.get(event_type, [])
        self._subscribers[event_type] = [*current, handler]

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Remove *handler* from *event_type*. No-op if not found."""
        current = self._subscribers.get(event_type, [])
        new_list = [h for h in current if h is not handler]
        if new_list:
            self._subscribers[event_type] = new_list
        else:
            self._subscribers.pop(event_type, None)

    def emit(self, event: HookEvent) -> int:
        """Call all matching handlers (exact match + ``'*'``).

        Returns count of handlers called. Never raises — handler errors
        are silently swallowed.
        """
        count = 0
        handlers: list[Callable] = []
        exact = self._subscribers.get(event.event_type, [])
        wildcard = self._subscribers.get("*", [])
        handlers = [*exact, *wildcard]
        for handler in handlers:
            try:
                handler(event)
                count += 1
            except Exception:
                count += 1  # still counts as called
        return count

    def subscriber_count(self, event_type: str) -> int:
        """Return number of subscribers for *event_type* (exact only, not wildcard)."""
        return len(self._subscribers.get(event_type, []))

    def clear(self) -> None:
        """Remove all subscribers."""
        self._subscribers = {}
