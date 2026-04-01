"""Tests for lidco.transcript.timeline."""
from __future__ import annotations

import time
from unittest.mock import patch

from lidco.transcript.timeline import SessionTimeline, TimelineEvent


class TestTimelineEvent:
    def test_frozen(self):
        ev = TimelineEvent(
            timestamp=1.0, event_type="cmd", label="test"
        )
        assert ev.detail == ""
        assert ev.duration_ms == 0.0
        try:
            ev.label = "other"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestSessionTimeline:
    def test_add_event(self):
        tl = SessionTimeline()
        ev = tl.add_event("command", "run tests", detail="pytest", duration_ms=120.0)
        assert ev.event_type == "command"
        assert ev.label == "run tests"
        assert ev.duration_ms == 120.0
        assert tl.event_count() == 1

    def test_get_events_all(self):
        tl = SessionTimeline()
        tl.add_event("cmd", "a")
        tl.add_event("llm", "b")
        tl.add_event("cmd", "c")
        assert len(tl.get_events()) == 3

    def test_get_events_filtered(self):
        tl = SessionTimeline()
        tl.add_event("cmd", "a")
        tl.add_event("llm", "b")
        tl.add_event("cmd", "c")
        assert len(tl.get_events("cmd")) == 2
        assert len(tl.get_events("llm")) == 1

    def test_render_text_empty(self):
        tl = SessionTimeline()
        assert tl.render_text() == "No events recorded."

    def test_render_text_with_events(self):
        tl = SessionTimeline()
        tl.add_event("cmd", "start", detail="init")
        tl.add_event("llm", "query", duration_ms=50.0)
        text = tl.render_text()
        assert "SESSION TIMELINE" in text
        assert "cmd" in text
        assert "llm" in text
        assert "50ms" in text

    def test_duration(self):
        tl = SessionTimeline()
        assert tl.duration() == 0.0
        with patch("lidco.transcript.timeline.time.time", side_effect=[100.0, 105.0]):
            tl.add_event("a", "first")
            tl.add_event("b", "second")
        assert tl.duration() == 5.0

    def test_event_count(self):
        tl = SessionTimeline()
        assert tl.event_count() == 0
        tl.add_event("x", "one")
        tl.add_event("y", "two")
        assert tl.event_count() == 2

    def test_summary_empty(self):
        tl = SessionTimeline()
        assert tl.summary() == "Empty timeline."

    def test_summary_with_events(self):
        tl = SessionTimeline()
        tl.add_event("cmd", "a")
        tl.add_event("cmd", "b")
        tl.add_event("llm", "c")
        s = tl.summary()
        assert "3 event(s)" in s
        assert "cmd: 2" in s
        assert "llm: 1" in s
