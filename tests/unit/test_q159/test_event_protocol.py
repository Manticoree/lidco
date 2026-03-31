"""Tests for Task 911 — Unified event bus protocol and adapters."""
from __future__ import annotations

import time

import pytest

from lidco.events.protocol import (
    UnifiedEvent,
    EventBusProtocol,
    DomainEventBusAdapter,
    AppEventBusAdapter,
)
from lidco.events.bus import EventBus
from lidco.domain.events import DomainEventPublisher


class TestUnifiedEvent:
    def test_frozen(self):
        evt = UnifiedEvent(event_type="test", payload={"k": 1})
        with pytest.raises(AttributeError):
            evt.event_type = "changed"  # type: ignore[misc]

    def test_defaults(self):
        evt = UnifiedEvent(event_type="t")
        assert evt.payload == {}
        assert evt.source == ""
        assert isinstance(evt.timestamp, float)
        assert len(evt.event_id) == 12

    def test_custom_fields(self):
        evt = UnifiedEvent(
            event_type="deploy",
            payload={"env": "prod"},
            timestamp=1000.0,
            event_id="abc123",
            source="ci",
        )
        assert evt.event_type == "deploy"
        assert evt.payload == {"env": "prod"}
        assert evt.timestamp == 1000.0
        assert evt.event_id == "abc123"
        assert evt.source == "ci"


class TestEventBusProtocolIsAbstract:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            EventBusProtocol()  # type: ignore[abstract]


class TestAppEventBusAdapter:
    """Adapter wrapping events.bus.EventBus."""

    def test_implements_protocol(self):
        bus = EventBus()
        adapter = AppEventBusAdapter(bus)
        assert isinstance(adapter, EventBusProtocol)

    def test_subscribe_and_publish(self):
        bus = EventBus()
        adapter = AppEventBusAdapter(bus)
        received: list[UnifiedEvent] = []

        # The handler gets an Event from bus, but subscribe goes through adapter
        def handler(event):
            pass  # adapter doesn't change handler signature

        sub_id = adapter.subscribe("test.event", handler)
        assert isinstance(sub_id, str)

        evt = adapter.publish("test.event", {"key": "value"})
        assert isinstance(evt, UnifiedEvent)
        assert evt.event_type == "test.event"
        assert evt.payload == {"key": "value"}

    def test_unsubscribe(self):
        bus = EventBus()
        adapter = AppEventBusAdapter(bus)
        sub_id = adapter.subscribe("evt", lambda e: None)
        assert adapter.unsubscribe(sub_id) is True
        assert adapter.unsubscribe(sub_id) is False

    def test_get_history(self):
        bus = EventBus()
        adapter = AppEventBusAdapter(bus)
        adapter.publish("a", {"x": 1})
        adapter.publish("b", {"y": 2})
        adapter.publish("a", {"x": 3})

        history = adapter.get_history()
        assert len(history) == 3

        filtered = adapter.get_history(event_type="a")
        assert len(filtered) == 2
        assert all(e.event_type == "a" for e in filtered)

    def test_get_history_limit(self):
        bus = EventBus()
        adapter = AppEventBusAdapter(bus)
        for i in range(10):
            adapter.publish("evt", {"i": i})

        history = adapter.get_history(limit=3)
        assert len(history) == 3


class TestDomainEventBusAdapter:
    """Adapter wrapping domain.events.DomainEventPublisher."""

    def test_implements_protocol(self):
        pub = DomainEventPublisher()
        adapter = DomainEventBusAdapter(pub)
        assert isinstance(adapter, EventBusProtocol)

    def test_subscribe_and_publish(self):
        pub = DomainEventPublisher()
        adapter = DomainEventBusAdapter(pub)
        received = []

        def handler(msg):
            received.append(msg)

        sub_id = adapter.subscribe("order.created", handler)
        assert isinstance(sub_id, str)

        evt = adapter.publish("order.created", {"order_id": "123"})
        assert isinstance(evt, UnifiedEvent)
        assert evt.event_type == "order.created"
        assert evt.payload == {"order_id": "123"}
        assert len(received) == 1

    def test_unsubscribe(self):
        pub = DomainEventPublisher()
        adapter = DomainEventBusAdapter(pub)
        sub_id = adapter.subscribe("evt", lambda m: None)
        assert adapter.unsubscribe(sub_id) is True
        assert adapter.unsubscribe(sub_id) is False

    def test_get_history(self):
        pub = DomainEventPublisher()
        adapter = DomainEventBusAdapter(pub)
        adapter.publish("a", {"x": 1})
        adapter.publish("b", {"y": 2})

        history = adapter.get_history()
        assert len(history) == 2

        filtered = adapter.get_history(event_type="a")
        assert len(filtered) == 1
        assert filtered[0].event_type == "a"

    def test_get_history_limit(self):
        pub = DomainEventPublisher()
        adapter = DomainEventBusAdapter(pub)
        for i in range(10):
            adapter.publish("evt", {"i": i})

        history = adapter.get_history(limit=3)
        assert len(history) == 3

    def test_unsubscribe_unknown_id(self):
        pub = DomainEventPublisher()
        adapter = DomainEventBusAdapter(pub)
        assert adapter.unsubscribe("nonexistent") is False
