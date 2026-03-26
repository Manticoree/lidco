"""Tests for src/lidco/domain/events.py — DomainEventPublisher, DomainEventMessage."""
import time
import pytest
from lidco.domain.events import DomainEventPublisher, DomainEventMessage


class TestDomainEventMessage:
    def test_create(self):
        msg = DomainEventMessage.create("OrderPlaced", {"order_id": "123"})
        assert msg.event_type == "OrderPlaced"
        assert msg.payload == {"order_id": "123"}
        assert len(msg.event_id) > 0
        assert msg.timestamp > 0

    def test_unique_ids(self):
        m1 = DomainEventMessage.create("E")
        m2 = DomainEventMessage.create("E")
        assert m1.event_id != m2.event_id


class TestDomainEventPublisher:
    def setup_method(self):
        self.pub = DomainEventPublisher()

    def test_subscribe_and_publish(self):
        received = []
        self.pub.subscribe("OrderPlaced", lambda e: received.append(e))
        self.pub.publish("OrderPlaced", {"order_id": "1"})
        assert len(received) == 1
        assert received[0].event_type == "OrderPlaced"

    def test_unsubscribe(self):
        received = []
        hid = self.pub.subscribe("OrderPlaced", lambda e: received.append(e))
        self.pub.unsubscribe("OrderPlaced", hid)
        self.pub.publish("OrderPlaced")
        assert received == []

    def test_unsubscribe_nonexistent(self):
        assert self.pub.unsubscribe("SomeEvent", "bad_id") is False

    def test_wildcard_subscriber(self):
        received = []
        self.pub.subscribe_wildcard(lambda e: received.append(e.event_type))
        self.pub.publish("EventA")
        self.pub.publish("EventB")
        assert "EventA" in received
        assert "EventB" in received

    def test_multiple_handlers(self):
        counts = [0, 0]
        self.pub.subscribe("E", lambda e: counts.__setitem__(0, counts[0] + 1))
        self.pub.subscribe("E", lambda e: counts.__setitem__(1, counts[1] + 1))
        self.pub.publish("E")
        assert counts == [1, 1]

    def test_handler_exception_captured(self):
        def bad_handler(e):
            raise RuntimeError("oops")
        self.pub.subscribe("E", bad_handler, handler_id="bad")
        self.pub.publish("E")  # should not raise
        errors = self.pub.last_errors
        assert len(errors) == 1
        assert errors[0][0] == "bad"

    def test_history(self):
        self.pub.publish("A")
        self.pub.publish("B")
        history = self.pub.history()
        assert len(history) == 2

    def test_history_newest_first(self):
        self.pub.publish("A")
        time.sleep(0.01)
        self.pub.publish("B")
        history = self.pub.history()
        assert history[0].event_type == "B"

    def test_history_by_type(self):
        self.pub.publish("A")
        self.pub.publish("B")
        self.pub.publish("A")
        history = self.pub.history(event_type="A")
        assert len(history) == 2
        assert all(e.event_type == "A" for e in history)

    def test_history_limit(self):
        for i in range(5):
            self.pub.publish("E")
        history = self.pub.history(limit=3)
        assert len(history) == 3

    def test_clear_history(self):
        self.pub.publish("E")
        n = self.pub.clear_history()
        assert n == 1
        assert self.pub.history() == []

    def test_handler_count(self):
        self.pub.subscribe("E", lambda e: None)
        self.pub.subscribe("E", lambda e: None)
        assert self.pub.handler_count("E") == 2

    def test_handler_count_zero_unknown(self):
        assert self.pub.handler_count("unknown") == 0

    def test_subscribed_types(self):
        self.pub.subscribe("TypeA", lambda e: None)
        self.pub.subscribe("TypeB", lambda e: None)
        types = self.pub.subscribed_types()
        assert "TypeA" in types
        assert "TypeB" in types

    def test_publish_event_directly(self):
        received = []
        self.pub.subscribe("DirectEvent", lambda e: received.append(e))
        msg = DomainEventMessage.create("DirectEvent", {"x": 1})
        self.pub.publish_event(msg)
        assert len(received) == 1

    def test_return_value_of_publish(self):
        msg = self.pub.publish("TestEvent", {"key": "val"})
        assert isinstance(msg, DomainEventMessage)
        assert msg.event_type == "TestEvent"
