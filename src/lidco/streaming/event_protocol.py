"""Typed event protocol for streaming output."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class EventType(str, Enum):
    """Types of stream events."""

    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    PROGRESS = "progress"
    SYSTEM = "system"
    DONE = "done"


@dataclass(frozen=True)
class StreamEvent:
    """A single typed stream event."""

    type: EventType
    data: str = ""
    timestamp: float = field(default_factory=time.time)
    event_id: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


class EventProtocol:
    """Serialize / deserialize stream events in JSON and SSE formats."""

    def __init__(self, version: str = "1.0") -> None:
        self._version = version

    @property
    def version(self) -> str:
        return self._version

    def create_event(
        self,
        event_type: EventType,
        data: str = "",
        metadata: dict[str, str] | None = None,
    ) -> StreamEvent:
        """Create a new :class:`StreamEvent` with a generated id."""
        meta_tuples: tuple[tuple[str, str], ...] = ()
        if metadata:
            meta_tuples = tuple(sorted(metadata.items()))
        return StreamEvent(
            type=event_type,
            data=data,
            timestamp=time.time(),
            event_id=uuid.uuid4().hex[:12],
            metadata=meta_tuples,
        )

    def serialize(self, event: StreamEvent) -> str:
        """Return a JSON string for *event*."""
        payload = {
            "type": event.type.value,
            "data": event.data,
            "timestamp": event.timestamp,
            "event_id": event.event_id,
            "metadata": dict(event.metadata),
        }
        return json.dumps(payload)

    def deserialize(self, raw: str) -> StreamEvent:
        """Parse a JSON string back into a :class:`StreamEvent`."""
        obj = json.loads(raw)
        meta = tuple(sorted(obj.get("metadata", {}).items()))
        return StreamEvent(
            type=EventType(obj["type"]),
            data=obj.get("data", ""),
            timestamp=obj.get("timestamp", 0.0),
            event_id=obj.get("event_id", ""),
            metadata=meta,
        )

    def format_sse(self, event: StreamEvent) -> str:
        """Format *event* as a Server-Sent Events message."""
        data_json = self.serialize(event)
        return f"event: {event.type.value}\ndata: {data_json}\n\n"

    def parse_sse(self, raw: str) -> StreamEvent | None:
        """Parse an SSE-formatted string back into a :class:`StreamEvent`."""
        data_line: str = ""
        for line in raw.strip().splitlines():
            if line.startswith("data: "):
                data_line = line[6:]
        if not data_line:
            return None
        return self.deserialize(data_line)
