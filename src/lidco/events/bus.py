"""EventBus — typed pub/sub event bus, thread-safe (stdlib only)."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Event:
    type: str
    data: dict
    timestamp: float = field(default_factory=time.time)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex


@dataclass
class Subscription:
    id: str
    event_type: str
    handler: Callable[[Event], None]


class EventBus:
    """
    Typed publish-subscribe event bus.

    Parameters
    ----------
    max_history:
        Maximum events retained in history per call to ``get_history``.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._max_history = max_history
        self._subscriptions: dict[str, list[Subscription]] = {}
        self._history: list[Event] = []
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- subscribe

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> str:
        """Register *handler* for *event_type*.  Return subscription ID."""
        sub_id = uuid.uuid4().hex
        sub = Subscription(id=sub_id, event_type=event_type, handler=handler)
        with self._lock:
            subs = list(self._subscriptions.get(event_type, []))
            subs.append(sub)
            self._subscriptions = {**self._subscriptions, event_type: subs}
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove subscription by ID.  Return True if found."""
        with self._lock:
            for event_type, subs in self._subscriptions.items():
                new_subs = [s for s in subs if s.id != subscription_id]
                if len(new_subs) < len(subs):
                    self._subscriptions = {**self._subscriptions, event_type: new_subs}
                    return True
        return False

    # ----------------------------------------------------------------- publish

    def publish(self, event_type: str, data: dict | None = None) -> Event:
        """
        Create an Event and call all subscribers synchronously.
        Handler exceptions are silently swallowed.
        Return the Event.
        """
        event = Event(type=event_type, data=data or {})

        with self._lock:
            handlers = list(self._subscriptions.get(event_type, []))
            self._history = [*self._history, event]
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        for sub in handlers:
            try:
                sub.handler(event)
            except Exception:  # noqa: BLE001
                pass

        return event

    def publish_async(self, event_type: str, data: dict | None = None) -> Event:
        """
        Create an Event and dispatch handlers in a background daemon thread.
        Return the Event immediately (before handlers run).
        """
        event = Event(type=event_type, data=data or {})

        with self._lock:
            handlers = list(self._subscriptions.get(event_type, []))
            self._history = [*self._history, event]
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        def _dispatch() -> None:
            for sub in handlers:
                try:
                    sub.handler(event)
                except Exception:  # noqa: BLE001
                    pass

        t = threading.Thread(target=_dispatch, daemon=True)
        t.start()
        return event

    # ----------------------------------------------------------------- history

    def get_history(self, event_type: str | None = None, limit: int = 50) -> list[Event]:
        """Return last *limit* events (newest first), optionally filtered by type."""
        with self._lock:
            events = list(self._history)

        if event_type is not None:
            events = [e for e in events if e.type == event_type]

        return list(reversed(events))[:limit]

    def clear_history(self) -> int:
        """Clear all history.  Return count cleared."""
        with self._lock:
            count = len(self._history)
            self._history = []
            return count

    # -------------------------------------------------------------- introspect

    def list_subscriptions(self, event_type: str | None = None) -> list[Subscription]:
        """Return subscriptions, optionally filtered by event_type."""
        with self._lock:
            if event_type is not None:
                return list(self._subscriptions.get(event_type, []))
            return [s for subs in self._subscriptions.values() for s in subs]

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._subscriptions.values())
