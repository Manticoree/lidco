"""Tests for lidco.streaming.event_protocol."""
from __future__ import annotations

import json

from lidco.streaming.event_protocol import EventProtocol, EventType, StreamEvent


class TestEventType:
    def test_all_members(self) -> None:
        names = {e.value for e in EventType}
        assert names == {"text", "tool_call", "tool_result", "error", "progress", "system", "done"}

    def test_str_enum(self) -> None:
        assert EventType.TEXT == "text"
        assert isinstance(EventType.ERROR, str)


class TestStreamEvent:
    def test_frozen(self) -> None:
        evt = StreamEvent(type=EventType.TEXT, data="hi")
        try:
            evt.data = "changed"  # type: ignore[misc]
            assert False, "should be frozen"
        except AttributeError:
            pass

    def test_defaults(self) -> None:
        evt = StreamEvent(type=EventType.DONE)
        assert evt.data == ""
        assert evt.metadata == ()


class TestEventProtocol:
    def test_version(self) -> None:
        proto = EventProtocol("2.0")
        assert proto.version == "2.0"

    def test_create_event(self) -> None:
        proto = EventProtocol()
        evt = proto.create_event(EventType.TEXT, "hello", {"key": "val"})
        assert evt.type == EventType.TEXT
        assert evt.data == "hello"
        assert evt.event_id != ""
        assert ("key", "val") in evt.metadata

    def test_serialize_deserialize(self) -> None:
        proto = EventProtocol()
        evt = proto.create_event(EventType.TOOL_CALL, "run ls")
        raw = proto.serialize(evt)
        parsed = proto.deserialize(raw)
        assert parsed.type == evt.type
        assert parsed.data == evt.data
        assert parsed.event_id == evt.event_id

    def test_deserialize_json_structure(self) -> None:
        proto = EventProtocol()
        evt = proto.create_event(EventType.ERROR, "oops")
        raw = proto.serialize(evt)
        obj = json.loads(raw)
        assert obj["type"] == "error"
        assert obj["data"] == "oops"

    def test_format_sse(self) -> None:
        proto = EventProtocol()
        evt = proto.create_event(EventType.SYSTEM, "init")
        sse = proto.format_sse(evt)
        assert sse.startswith("event: system\n")
        assert "data: " in sse
        assert sse.endswith("\n\n")

    def test_parse_sse(self) -> None:
        proto = EventProtocol()
        evt = proto.create_event(EventType.PROGRESS, "50%")
        sse = proto.format_sse(evt)
        parsed = proto.parse_sse(sse)
        assert parsed is not None
        assert parsed.type == EventType.PROGRESS
        assert parsed.data == "50%"

    def test_parse_sse_invalid(self) -> None:
        proto = EventProtocol()
        assert proto.parse_sse("garbage") is None

    def test_metadata_sorted(self) -> None:
        proto = EventProtocol()
        evt = proto.create_event(EventType.TEXT, "", {"z": "1", "a": "2"})
        assert evt.metadata == (("a", "2"), ("z", "1"))
