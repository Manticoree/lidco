"""Tests for lidco.streaming.event_replay."""
from __future__ import annotations

from lidco.streaming.event_replay import EventReplay, ReplayEntry


class TestReplayEntry:
    def test_frozen(self) -> None:
        e = ReplayEntry(event_data="d")
        try:
            e.event_data = "x"  # type: ignore[misc]
            assert False, "should be frozen"
        except AttributeError:
            pass

    def test_defaults(self) -> None:
        e = ReplayEntry(event_data="d")
        assert e.event_type == ""


class TestEventReplay:
    def test_start_stop(self) -> None:
        r = EventReplay()
        assert r.recording is False
        r.start_recording()
        assert r.recording is True
        count = r.stop_recording()
        assert count == 0
        assert r.recording is False

    def test_record_when_active(self) -> None:
        r = EventReplay()
        r.start_recording()
        entry = r.record("evt1", "text")
        assert entry is not None
        assert entry.event_data == "evt1"

    def test_record_when_inactive(self) -> None:
        r = EventReplay()
        assert r.record("evt") is None

    def test_replay_slice(self) -> None:
        r = EventReplay()
        r.start_recording()
        r.record("a")
        r.record("b")
        r.record("c")
        result = r.replay(1, 3)
        assert len(result) == 2
        assert result[0].event_data == "b"

    def test_filter_by_type(self) -> None:
        r = EventReplay()
        r.start_recording()
        r.record("e1", "text")
        r.record("e2", "error")
        r.record("e3", "text")
        filtered = r.filter_by_type("text")
        assert len(filtered) == 2

    def test_seek(self) -> None:
        r = EventReplay()
        r.start_recording()
        r.record("old")
        import time
        ts = time.time()
        r.record("new")
        result = r.seek(ts)
        assert len(result) >= 1

    def test_export(self) -> None:
        r = EventReplay()
        r.start_recording()
        r.record("d", "t")
        exported = r.export()
        assert len(exported) == 1
        assert exported[0]["event_data"] == "d"
        assert exported[0]["event_type"] == "t"

    def test_clear(self) -> None:
        r = EventReplay()
        r.start_recording()
        r.record("x")
        r.clear()
        assert r.replay() == []

    def test_summary_empty(self) -> None:
        r = EventReplay()
        assert "empty" in r.summary()

    def test_summary_with_entries(self) -> None:
        r = EventReplay()
        r.start_recording()
        r.record("a", "text")
        r.record("b", "error")
        s = r.summary()
        assert "2 entries" in s
        assert "text=1" in s
