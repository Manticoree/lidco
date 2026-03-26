"""AggregateRoot — base class for event-sourced domain aggregates (stdlib only)."""
from __future__ import annotations

from typing import Any
from lidco.eventsourcing.store import DomainEvent


class AggregateRoot:
    """
    Base class for event-sourced aggregates.

    Subclasses define ``apply_<EventType>`` methods to handle events.
    Uncommitted events are accumulated in ``_pending_events`` and cleared
    after they are persisted via :meth:`mark_committed`.

    Example::

        class OrderAggregate(AggregateRoot):
            def __init__(self):
                super().__init__()
                self.status = "new"

            def place(self, order_id: str):
                event = self._create_event("OrderPlaced", {"order_id": order_id})
                self._apply_event(event)
                return event

            def apply_OrderPlaced(self, event: DomainEvent):
                self.status = "placed"
    """

    aggregate_type: str = "Aggregate"

    def __init__(self, aggregate_id: str = "") -> None:
        self._aggregate_id = aggregate_id
        self._version: int = 0
        self._pending_events: list[DomainEvent] = []

    @property
    def aggregate_id(self) -> str:
        return self._aggregate_id

    @property
    def version(self) -> int:
        return self._version

    @property
    def pending_events(self) -> list[DomainEvent]:
        return list(self._pending_events)

    def _create_event(
        self, event_type: str, payload: dict[str, Any] | None = None
    ) -> DomainEvent:
        """Create a new domain event for this aggregate."""
        self._version += 1
        return DomainEvent.create(
            aggregate_id=self._aggregate_id,
            aggregate_type=self.aggregate_type,
            event_type=event_type,
            version=self._version,
            payload=payload,
        )

    def _apply_event(self, event: DomainEvent) -> None:
        """Apply *event* by calling the matching ``apply_<EventType>`` method."""
        handler_name = f"apply_{event.event_type}"
        handler = getattr(self, handler_name, None)
        if handler is not None:
            handler(event)
        self._pending_events = [*self._pending_events, event]

    def load_from_history(self, events: list[DomainEvent]) -> None:
        """Replay a list of persisted events to rebuild state."""
        self._pending_events = []
        for event in events:
            self._version = event.version
            handler_name = f"apply_{event.event_type}"
            handler = getattr(self, handler_name, None)
            if handler is not None:
                handler(event)

    def mark_committed(self) -> None:
        """Clear pending events after they have been persisted."""
        self._pending_events = []

    def has_pending_events(self) -> bool:
        return len(self._pending_events) > 0
