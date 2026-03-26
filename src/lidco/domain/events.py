"""DomainEventPublisher — sync/async domain event dispatch with handler registry (stdlib only)."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable
import time
import uuid


@dataclass
class DomainEventMessage:
    """A publishable domain event message."""
    event_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: float
    source: str = ""

    @classmethod
    def create(
        cls,
        event_type: str,
        payload: dict[str, Any] | None = None,
        source: str = "",
    ) -> "DomainEventMessage":
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            payload=dict(payload or {}),
            timestamp=time.time(),
            source=source,
        )


class DomainEventPublisher:
    """
    Synchronous domain event publisher with named handler registration.

    Handlers are called in registration order.
    Handler exceptions are collected and available via ``last_errors``.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[tuple[str, Callable]]] = {}
        self._history: list[DomainEventMessage] = []
        self._errors: list[tuple[str, Exception]] = []
        self._lock = threading.Lock()

    # -------------------------------------------------------------- subscribe

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEventMessage], None],
        handler_id: str | None = None,
    ) -> str:
        """
        Subscribe *handler* to events of *event_type*.

        Returns the handler_id (auto-generated if not provided).
        """
        hid = handler_id or str(uuid.uuid4())
        with self._lock:
            current = self._handlers.get(event_type, [])
            self._handlers = {
                **self._handlers,
                event_type: [*current, (hid, handler)],
            }
        return hid

    def unsubscribe(self, event_type: str, handler_id: str) -> bool:
        """Remove handler by id.  Return True if it existed."""
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            new_handlers = [(hid, h) for hid, h in handlers if hid != handler_id]
            if len(new_handlers) == len(handlers):
                return False
            self._handlers = {**self._handlers, event_type: new_handlers}
        return True

    def subscribe_wildcard(
        self,
        handler: Callable[[DomainEventMessage], None],
        handler_id: str | None = None,
    ) -> str:
        """Subscribe to ALL event types (wildcard handler)."""
        return self.subscribe("*", handler, handler_id)

    # --------------------------------------------------------------- publish

    def publish(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        source: str = "",
    ) -> DomainEventMessage:
        """
        Publish an event synchronously.

        Calls all handlers registered for *event_type* and all wildcard handlers.
        Exceptions in handlers are captured in :attr:`last_errors`.
        """
        msg = DomainEventMessage.create(event_type, payload, source)
        with self._lock:
            type_handlers = list(self._handlers.get(event_type, []))
            wildcard = list(self._handlers.get("*", []))
            self._history = [*self._history, msg]

        errors = []
        for hid, handler in type_handlers + wildcard:
            try:
                handler(msg)
            except Exception as exc:
                errors.append((hid, exc))

        if errors:
            with self._lock:
                self._errors = [*self._errors, *errors]

        return msg

    def publish_event(self, event: DomainEventMessage) -> None:
        """Publish a pre-built :class:`DomainEventMessage`."""
        with self._lock:
            type_handlers = list(self._handlers.get(event.event_type, []))
            wildcard = list(self._handlers.get("*", []))
            self._history = [*self._history, event]

        errors = []
        for hid, handler in type_handlers + wildcard:
            try:
                handler(event)
            except Exception as exc:
                errors.append((hid, exc))

        if errors:
            with self._lock:
                self._errors = [*self._errors, *errors]

    # ----------------------------------------------------------------- query

    def history(
        self, event_type: str | None = None, limit: int | None = None
    ) -> list[DomainEventMessage]:
        """Return published events (newest first)."""
        with self._lock:
            events = list(self._history)
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        events.sort(key=lambda e: e.timestamp, reverse=True)
        if limit is not None:
            events = events[:limit]
        return events

    def clear_history(self) -> int:
        with self._lock:
            n = len(self._history)
            self._history = []
        return n

    @property
    def last_errors(self) -> list[tuple[str, Exception]]:
        with self._lock:
            return list(self._errors)

    def clear_errors(self) -> None:
        with self._lock:
            self._errors = []

    def handler_count(self, event_type: str) -> int:
        with self._lock:
            return len(self._handlers.get(event_type, []))

    def subscribed_types(self) -> list[str]:
        with self._lock:
            return [t for t, handlers in self._handlers.items() if handlers]
