"""Visual timeline of session events."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class TimelineEvent:
    """A single event on the session timeline."""

    timestamp: float
    event_type: str
    label: str
    detail: str = ""
    duration_ms: float = 0.0


class SessionTimeline:
    """Ordered timeline of session events."""

    def __init__(self) -> None:
        self._events: list[TimelineEvent] = []

    def add_event(
        self,
        event_type: str,
        label: str,
        detail: str = "",
        duration_ms: float = 0.0,
    ) -> TimelineEvent:
        """Add an event to the timeline."""
        event = TimelineEvent(
            timestamp=time.time(),
            event_type=event_type,
            label=label,
            detail=detail,
            duration_ms=duration_ms,
        )
        self._events.append(event)
        return event

    def get_events(self, event_type: str | None = None) -> list[TimelineEvent]:
        """Return events, optionally filtered by type."""
        if event_type is None:
            return list(self._events)
        return [e for e in self._events if e.event_type == event_type]

    def render_text(self, width: int = 80) -> str:
        """Render a text-based timeline."""
        if not self._events:
            return "No events recorded."
        lines: list[str] = []
        lines.append("=" * width)
        lines.append("SESSION TIMELINE".center(width))
        lines.append("=" * width)
        for i, event in enumerate(self._events):
            ts = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
            prefix = f"[{ts}] [{event.event_type}]"
            line = f"{prefix} {event.label}"
            if event.detail:
                line += f" — {event.detail}"
            if event.duration_ms > 0:
                line += f" ({event.duration_ms:.0f}ms)"
            lines.append(line)
            if i < len(self._events) - 1:
                lines.append("  |")
        lines.append("=" * width)
        return "\n".join(lines)

    def duration(self) -> float:
        """Total session duration in seconds."""
        if len(self._events) < 2:
            return 0.0
        return self._events[-1].timestamp - self._events[0].timestamp

    def event_count(self) -> int:
        """Return total number of events."""
        return len(self._events)

    def summary(self) -> str:
        """Return a short text summary of the timeline."""
        if not self._events:
            return "Empty timeline."
        type_counts: dict[str, int] = {}
        for e in self._events:
            type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1
        parts = [f"{k}: {v}" for k, v in sorted(type_counts.items())]
        dur = self.duration()
        return (
            f"{self.event_count()} event(s) over {dur:.1f}s — {', '.join(parts)}"
        )
