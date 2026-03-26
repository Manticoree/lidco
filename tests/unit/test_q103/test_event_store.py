"""Tests for src/lidco/eventsourcing/store.py — EventStore, DomainEvent, Snapshot."""
import time
import pytest
from lidco.eventsourcing.store import (
    EventStore, DomainEvent, Snapshot, OptimisticConcurrencyError,
)


def make_event(agg_id="agg1", event_type="Created", version=1, payload=None):
    return DomainEvent.create(
        aggregate_id=agg_id,
        aggregate_type="TestAggregate",
        event_type=event_type,
        version=version,
        payload=payload or {},
    )


class TestDomainEvent:
    def test_create_fields(self):
        e = make_event()
        assert e.aggregate_id == "agg1"
        assert e.event_type == "Created"
        assert e.version == 1
        assert len(e.event_id) > 0
        assert e.timestamp > 0

    def test_unique_event_ids(self):
        e1 = make_event()
        e2 = make_event()
        assert e1.event_id != e2.event_id


class TestEventStoreBasic:
    def setup_method(self):
        self.store = EventStore(path=None)

    def test_append_and_load(self):
        e = make_event()
        self.store.append(e)
        events = self.store.load("agg1")
        assert len(events) == 1
        assert events[0].event_type == "Created"

    def test_load_empty(self):
        assert self.store.load("nonexistent") == []

    def test_count(self):
        self.store.append(make_event(version=1))
        self.store.append(make_event(version=2, event_type="Updated"))
        assert self.store.count() == 2

    def test_get_all(self):
        self.store.append(make_event())
        events = self.store.get_all()
        assert len(events) == 1

    def test_current_version(self):
        self.store.append(make_event(version=1))
        self.store.append(make_event(version=2, event_type="Updated"))
        assert self.store.current_version("agg1") == 2

    def test_current_version_zero_for_unknown(self):
        assert self.store.current_version("unknown") == 0

    def test_load_from_version(self):
        self.store.append(make_event(version=1))
        self.store.append(make_event(version=2, event_type="Updated"))
        self.store.append(make_event(version=3, event_type="Deleted"))
        events = self.store.load_from_version("agg1", 2)
        assert len(events) == 2
        assert events[0].version == 2

    def test_load_by_type(self):
        self.store.append(make_event(version=1, event_type="Created"))
        self.store.append(make_event(agg_id="agg2", version=1, event_type="Created"))
        self.store.append(make_event(version=2, event_type="Updated"))
        events = self.store.load_by_type("Created")
        assert len(events) == 2

    def test_clear(self):
        self.store.append(make_event())
        self.store.clear()
        assert self.store.count() == 0

    def test_append_many(self):
        events = [
            make_event(version=1, event_type="Created"),
            make_event(version=2, event_type="Updated"),
        ]
        self.store.append_many(events)
        assert self.store.count() == 2

    def test_append_many_empty(self):
        self.store.append_many([])
        assert self.store.count() == 0


class TestOptimisticConcurrency:
    def setup_method(self):
        self.store = EventStore(path=None)

    def test_expected_version_matches(self):
        self.store.append(make_event(version=1))
        # expected_version=1 should pass
        self.store.append(make_event(version=2, event_type="Updated"), expected_version=1)
        assert self.store.count() == 2

    def test_expected_version_mismatch_raises(self):
        self.store.append(make_event(version=1))
        with pytest.raises(OptimisticConcurrencyError) as exc_info:
            self.store.append(make_event(version=2), expected_version=5)
        assert exc_info.value.aggregate_id == "agg1"
        assert exc_info.value.expected == 5
        assert exc_info.value.actual == 1

    def test_expected_zero_for_new_aggregate(self):
        event = make_event(agg_id="new_agg", version=1)
        self.store.append(event, expected_version=0)
        assert self.store.count() == 1


class TestSnapshots:
    def setup_method(self):
        self.store = EventStore(path=None)

    def test_save_and_get_snapshot(self):
        snap = Snapshot(
            aggregate_id="agg1",
            aggregate_type="Test",
            version=5,
            timestamp=time.time(),
            state={"status": "active"},
        )
        self.store.save_snapshot(snap)
        result = self.store.get_snapshot("agg1")
        assert result is not None
        assert result.version == 5
        assert result.state["status"] == "active"

    def test_get_snapshot_missing(self):
        assert self.store.get_snapshot("nonexistent") is None

    def test_overwrite_snapshot(self):
        snap1 = Snapshot("agg1", "T", 5, time.time(), {"v": 5})
        snap2 = Snapshot("agg1", "T", 10, time.time(), {"v": 10})
        self.store.save_snapshot(snap1)
        self.store.save_snapshot(snap2)
        result = self.store.get_snapshot("agg1")
        assert result.version == 10


class TestEventStorePersistence:
    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "events.json"
        store1 = EventStore(path=path)
        store1.append(make_event(version=1))

        store2 = EventStore(path=path)
        assert store2.count() == 1

    def test_snapshot_persisted(self, tmp_path):
        path = tmp_path / "events.json"
        store1 = EventStore(path=path)
        snap = Snapshot("agg1", "T", 3, time.time(), {"x": 1})
        store1.save_snapshot(snap)

        store2 = EventStore(path=path)
        result = store2.get_snapshot("agg1")
        assert result is not None
        assert result.version == 3
