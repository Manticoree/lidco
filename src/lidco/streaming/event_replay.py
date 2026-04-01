"""Record and replay stream events for debugging."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReplayEntry:
    """A single recorded event."""

    event_data: str
    timestamp: float = field(default_factory=time.time)
    event_type: str = ""


class EventReplay:
    """Record a journal of stream events and replay / filter them."""

    def __init__(self) -> None:
        self._journal: list[ReplayEntry] = []
        self._recording: bool = False

    @property
    def recording(self) -> bool:
        """Whether recording is active."""
        return self._recording

    def start_recording(self) -> None:
        """Begin recording events."""
        self._recording = True

    def stop_recording(self) -> int:
        """Stop recording and return the number of events captured."""
        self._recording = False
        return len(self._journal)

    def record(self, event_data: str, event_type: str = "") -> ReplayEntry | None:
        """Record an event if recording is active.  Returns ``None`` otherwise."""
        if not self._recording:
            return None
        entry = ReplayEntry(
            event_data=event_data,
            timestamp=time.time(),
            event_type=event_type,
        )
        self._journal = [*self._journal, entry]
        return entry

    def replay(
        self,
        start: int = 0,
        end: int | None = None,
    ) -> list[ReplayEntry]:
        """Return a slice of the journal."""
        return list(self._journal[start:end])

    def filter_by_type(self, event_type: str) -> list[ReplayEntry]:
        """Return entries matching *event_type*."""
        return [e for e in self._journal if e.event_type == event_type]

    def seek(self, timestamp: float) -> list[ReplayEntry]:
        """Return events recorded after *timestamp*."""
        return [e for e in self._journal if e.timestamp >= timestamp]

    def export(self) -> list[dict[str, object]]:
        """Export journal as a list of plain dicts."""
        return [
            {
                "event_data": e.event_data,
                "timestamp": e.timestamp,
                "event_type": e.event_type,
            }
            for e in self._journal
        ]

    def clear(self) -> None:
        """Clear the journal."""
        self._journal = []

    def summary(self) -> str:
        """Human-readable summary."""
        if not self._journal:
            return "EventReplay: empty journal."
        types: dict[str, int] = {}
        for e in self._journal:
            key = e.event_type or "(untyped)"
            types = {**types, key: types.get(key, 0) + 1}
        parts = ", ".join(f"{k}={v}" for k, v in types.items())
        state = "recording" if self._recording else "stopped"
        return f"EventReplay [{state}]: {len(self._journal)} entries ({parts})"
