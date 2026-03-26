"""Tests for src/lidco/patterns/observer.py — Observable, ObservableValue, ObservableList."""
import pytest
from lidco.patterns.observer import Observable, ObservableValue, ObservableList


class TestObservable:
    def test_add_and_notify(self):
        obs = Observable()
        events = []
        obs.add_observer("listener", lambda e, **kw: events.append((e, kw)))
        count = obs.notify("change", x=1)
        assert count == 1
        assert events == [("change", {"x": 1})]

    def test_remove_observer(self):
        obs = Observable()
        obs.add_observer("a", lambda e, **kw: None)
        removed = obs.remove_observer("a")
        assert removed is True
        assert obs.observer_count == 0

    def test_remove_nonexistent(self):
        obs = Observable()
        assert obs.remove_observer("missing") is False

    def test_observer_count(self):
        obs = Observable()
        obs.add_observer("a", lambda e, **kw: None)
        obs.add_observer("b", lambda e, **kw: None)
        assert obs.observer_count == 2

    def test_notify_swallows_exceptions(self):
        obs = Observable()
        def bad_listener(e, **kw):
            raise RuntimeError("oops")
        obs.add_observer("bad", bad_listener)
        count = obs.notify("event")  # should not raise
        assert count == 1

    def test_overwrite_observer(self):
        obs = Observable()
        calls_a = []
        calls_b = []
        obs.add_observer("key", lambda e, **kw: calls_a.append(e))
        obs.add_observer("key", lambda e, **kw: calls_b.append(e))
        obs.notify("test")
        assert calls_a == []
        assert calls_b == ["test"]

    def test_no_observers_notify(self):
        obs = Observable()
        assert obs.notify("event") == 0


class TestObservableValue:
    def test_initial_value(self):
        v = ObservableValue(42)
        assert v.value == 42

    def test_set_value_notifies(self):
        v = ObservableValue(0)
        events = []
        v.add_observer("watcher", lambda e, **kw: events.append(kw))
        v.value = 1
        assert events == [{"old": 0, "new": 1}]

    def test_set_same_value_no_notification(self):
        v = ObservableValue(5)
        events = []
        v.add_observer("w", lambda e, **kw: events.append(e))
        v.value = 5
        assert events == []

    def test_multiple_changes(self):
        v = ObservableValue("a")
        changes = []
        v.add_observer("t", lambda e, **kw: changes.append((kw["old"], kw["new"])))
        v.value = "b"
        v.value = "c"
        assert changes == [("a", "b"), ("b", "c")]


class TestObservableList:
    def test_append_notifies(self):
        lst = ObservableList()
        events = []
        lst.add_observer("w", lambda e, **kw: events.append((e, kw)))
        lst.append("x")
        assert events[0][0] == "append"
        assert events[0][1]["item"] == "x"

    def test_remove_notifies(self):
        lst = ObservableList(["a", "b"])
        events = []
        lst.add_observer("w", lambda e, **kw: events.append(e))
        lst.remove("a")
        assert "remove" in events

    def test_remove_missing_raises(self):
        lst = ObservableList()
        with pytest.raises(ValueError):
            lst.remove("nonexistent")

    def test_clear_notifies(self):
        lst = ObservableList([1, 2, 3])
        events = []
        lst.add_observer("w", lambda e, **kw: events.append((e, kw)))
        lst.clear()
        assert events[0][0] == "clear"
        assert events[0][1]["count"] == 3

    def test_len(self):
        lst = ObservableList([1, 2])
        assert len(lst) == 2
        lst.append(3)
        assert len(lst) == 3

    def test_getitem(self):
        lst = ObservableList([10, 20])
        assert lst[0] == 10

    def test_iter(self):
        lst = ObservableList([1, 2, 3])
        assert list(lst) == [1, 2, 3]

    def test_contains(self):
        lst = ObservableList([1, 2])
        assert 1 in lst
        assert 99 not in lst

    def test_items_returns_copy(self):
        lst = ObservableList([1, 2])
        copy = lst.items
        copy.append(99)
        assert len(lst) == 2

    def test_initial_from_list(self):
        lst = ObservableList([4, 5, 6])
        assert list(lst) == [4, 5, 6]
