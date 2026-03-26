"""Tests for T629 EventBus."""
import time
from unittest.mock import MagicMock

import pytest

from lidco.events.bus import Event, EventBus


class TestEventBus:
    def test_subscribe_returns_id(self):
        bus = EventBus()
        sid = bus.subscribe("test", lambda e: None)
        assert isinstance(sid, str) and len(sid) > 0

    def test_publish_calls_handler(self):
        bus = EventBus()
        received = []
        bus.subscribe("click", received.append)
        bus.publish("click", {"x": 1})
        assert len(received) == 1
        assert received[0].type == "click"
        assert received[0].data == {"x": 1}

    def test_publish_multiple_handlers(self):
        bus = EventBus()
        calls_a, calls_b = [], []
        bus.subscribe("evt", calls_a.append)
        bus.subscribe("evt", calls_b.append)
        bus.publish("evt")
        assert len(calls_a) == 1
        assert len(calls_b) == 1

    def test_unsubscribe_removes_handler(self):
        bus = EventBus()
        received = []
        sid = bus.subscribe("x", received.append)
        bus.unsubscribe(sid)
        bus.publish("x")
        assert received == []

    def test_unsubscribe_unknown_returns_false(self):
        bus = EventBus()
        assert bus.unsubscribe("nonexistent") is False

    def test_get_history_returns_events(self):
        bus = EventBus()
        bus.publish("a")
        bus.publish("b")
        bus.publish("c")
        history = bus.get_history()
        assert len(history) == 3

    def test_get_history_newest_first(self):
        bus = EventBus()
        bus.publish("first")
        bus.publish("second")
        history = bus.get_history()
        assert history[0].type == "second"

    def test_get_history_filters_by_type(self):
        bus = EventBus()
        bus.publish("a")
        bus.publish("b")
        bus.publish("a")
        history = bus.get_history("a")
        assert len(history) == 2
        assert all(e.type == "a" for e in history)

    def test_get_history_limit(self):
        bus = EventBus()
        for _ in range(10):
            bus.publish("x")
        assert len(bus.get_history(limit=3)) == 3

    def test_clear_history_returns_count(self):
        bus = EventBus()
        bus.publish("x")
        bus.publish("y")
        count = bus.clear_history()
        assert count == 2
        assert bus.get_history() == []

    def test_publish_async_calls_handler(self):
        bus = EventBus()
        received = []
        bus.subscribe("async_evt", received.append)
        bus.publish_async("async_evt", {"key": "val"})
        time.sleep(0.1)
        assert len(received) == 1

    def test_handler_exception_does_not_propagate(self):
        bus = EventBus()

        def bad_handler(e):
            raise RuntimeError("oops")

        bus.subscribe("boom", bad_handler)
        # Should not raise
        bus.publish("boom")

    def test_event_auto_id(self):
        e = Event(type="test", data={})
        assert e.id and len(e.id) > 0

    def test_subscriber_count(self):
        bus = EventBus()
        bus.subscribe("a", lambda e: None)
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        assert bus.subscriber_count == 3

    def test_publish_returns_event(self):
        bus = EventBus()
        e = bus.publish("my_event", {"k": "v"})
        assert e.type == "my_event"
        assert e.data == {"k": "v"}
