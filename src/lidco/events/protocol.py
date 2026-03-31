"""Unified event bus protocol -- Q159.

Defines an abstract EventBusProtocol and adapter classes that wrap the existing
DomainEventPublisher (domain/events.py) and EventBus (events/bus.py).
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Canonical event type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnifiedEvent:
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = ""


# ---------------------------------------------------------------------------
# Abstract protocol
# ---------------------------------------------------------------------------

class EventBusProtocol(ABC):
    """Common interface that all event buses in LIDCO must satisfy."""

    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable) -> str:
        """Subscribe *handler* to *event_type*.  Return a subscription ID."""
        ...

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription by ID.  Return True if it existed."""
        ...

    @abstractmethod
    def publish(self, event_type: str, payload: dict | None = None) -> UnifiedEvent:
        """Publish an event and return it as a :class:`UnifiedEvent`."""
        ...

    @abstractmethod
    def get_history(
        self, event_type: str | None = None, limit: int = 50
    ) -> list[UnifiedEvent]:
        """Return recent events, optionally filtered by type."""
        ...


# ---------------------------------------------------------------------------
# Adapter: DomainEventPublisher  ->  EventBusProtocol
# ---------------------------------------------------------------------------

class DomainEventBusAdapter(EventBusProtocol):
    """Wrap :class:`lidco.domain.events.DomainEventPublisher` behind :class:`EventBusProtocol`."""

    def __init__(self, publisher: Any) -> None:
        self._publisher = publisher
        # Map subscription_id -> (event_type, handler_id) for unsubscribe
        self._sub_map: dict[str, tuple[str, str]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> str:
        """Subscribe via the underlying DomainEventPublisher."""
        # DomainEventPublisher.subscribe returns a handler_id
        handler_id = self._publisher.subscribe(event_type, handler)
        sub_id = uuid.uuid4().hex[:12]
        self._sub_map = {**self._sub_map, sub_id: (event_type, handler_id)}
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        entry = self._sub_map.get(subscription_id)
        if entry is None:
            return False
        event_type, handler_id = entry
        removed = self._publisher.unsubscribe(event_type, handler_id)
        if removed:
            self._sub_map = {
                k: v for k, v in self._sub_map.items() if k != subscription_id
            }
        return removed

    def publish(self, event_type: str, payload: dict | None = None) -> UnifiedEvent:
        msg = self._publisher.publish(event_type, payload or {})
        return UnifiedEvent(
            event_type=msg.event_type,
            payload=dict(msg.payload),
            timestamp=msg.timestamp,
            event_id=msg.event_id,
            source=msg.source,
        )

    def get_history(
        self, event_type: str | None = None, limit: int = 50
    ) -> list[UnifiedEvent]:
        msgs = self._publisher.history(event_type=event_type, limit=limit)
        return [
            UnifiedEvent(
                event_type=m.event_type,
                payload=dict(m.payload),
                timestamp=m.timestamp,
                event_id=m.event_id,
                source=m.source,
            )
            for m in msgs
        ]


# ---------------------------------------------------------------------------
# Adapter: EventBus  ->  EventBusProtocol
# ---------------------------------------------------------------------------

class AppEventBusAdapter(EventBusProtocol):
    """Wrap :class:`lidco.events.bus.EventBus` behind :class:`EventBusProtocol`."""

    def __init__(self, bus: Any) -> None:
        self._bus = bus

    def subscribe(self, event_type: str, handler: Callable) -> str:
        return self._bus.subscribe(event_type, handler)

    def unsubscribe(self, subscription_id: str) -> bool:
        return self._bus.unsubscribe(subscription_id)

    def publish(self, event_type: str, payload: dict | None = None) -> UnifiedEvent:
        event = self._bus.publish(event_type, payload)
        return UnifiedEvent(
            event_type=event.type,
            payload=dict(event.data),
            timestamp=event.timestamp,
            event_id=event.id,
            source="",
        )

    def get_history(
        self, event_type: str | None = None, limit: int = 50
    ) -> list[UnifiedEvent]:
        events = self._bus.get_history(event_type=event_type, limit=limit)
        return [
            UnifiedEvent(
                event_type=e.type,
                payload=dict(e.data),
                timestamp=e.timestamp,
                event_id=e.id,
                source="",
            )
            for e in events
        ]
