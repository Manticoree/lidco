"""Tests for src/lidco/eventsourcing/aggregate.py — AggregateRoot."""
import pytest
from lidco.eventsourcing.aggregate import AggregateRoot
from lidco.eventsourcing.store import DomainEvent


class OrderAggregate(AggregateRoot):
    aggregate_type = "Order"

    def __init__(self, aggregate_id: str = ""):
        super().__init__(aggregate_id)
        self.status = "new"
        self.items: list[str] = []

    def place(self):
        event = self._create_event("OrderPlaced", {"status": "placed"})
        self._apply_event(event)

    def add_item(self, item: str):
        event = self._create_event("ItemAdded", {"item": item})
        self._apply_event(event)

    def cancel(self):
        event = self._create_event("OrderCancelled")
        self._apply_event(event)

    def apply_OrderPlaced(self, event: DomainEvent):
        self.status = "placed"

    def apply_ItemAdded(self, event: DomainEvent):
        self.items.append(event.payload.get("item", ""))

    def apply_OrderCancelled(self, event: DomainEvent):
        self.status = "cancelled"


class TestAggregateRoot:
    def test_initial_state(self):
        agg = OrderAggregate("order-1")
        assert agg.aggregate_id == "order-1"
        assert agg.version == 0
        assert agg.pending_events == []

    def test_apply_event_increments_version(self):
        agg = OrderAggregate("order-1")
        agg.place()
        assert agg.version == 1

    def test_apply_event_changes_state(self):
        agg = OrderAggregate("order-1")
        agg.place()
        assert agg.status == "placed"

    def test_pending_events_accumulated(self):
        agg = OrderAggregate("order-1")
        agg.place()
        agg.add_item("widget")
        assert len(agg.pending_events) == 2

    def test_mark_committed_clears_pending(self):
        agg = OrderAggregate("order-1")
        agg.place()
        agg.mark_committed()
        assert agg.pending_events == []

    def test_has_pending_events(self):
        agg = OrderAggregate("order-1")
        assert not agg.has_pending_events()
        agg.place()
        assert agg.has_pending_events()

    def test_load_from_history_rebuilds_state(self):
        agg1 = OrderAggregate("order-1")
        agg1.place()
        agg1.add_item("widget")
        history = agg1.pending_events

        agg2 = OrderAggregate("order-1")
        agg2.load_from_history(history)
        assert agg2.status == "placed"
        assert "widget" in agg2.items
        assert agg2.version == 2

    def test_load_from_history_clears_pending(self):
        agg1 = OrderAggregate("order-1")
        agg1.place()
        history = agg1.pending_events

        agg2 = OrderAggregate("order-1")
        agg2.load_from_history(history)
        assert agg2.pending_events == []

    def test_event_type_set_correctly(self):
        agg = OrderAggregate("order-1")
        agg.place()
        event = agg.pending_events[0]
        assert event.event_type == "OrderPlaced"
        assert event.aggregate_id == "order-1"
        assert event.aggregate_type == "Order"

    def test_unknown_event_type_no_error(self):
        agg = OrderAggregate("order-1")
        event = agg._create_event("UnknownEvent")
        agg._apply_event(event)  # No apply_UnknownEvent method — should not raise
        assert agg.version == 1

    def test_multiple_items(self):
        agg = OrderAggregate("order-1")
        agg.place()
        agg.add_item("a")
        agg.add_item("b")
        assert len(agg.items) == 2
        assert agg.version == 3

    def test_cancel_changes_status(self):
        agg = OrderAggregate("order-1")
        agg.place()
        agg.cancel()
        assert agg.status == "cancelled"
