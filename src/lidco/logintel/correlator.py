"""Log Correlator — correlate logs across services for request tracing.

Supports timeline reconstruction and root-cause chain analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from lidco.logintel.parser import LogEntry


@dataclass(frozen=True)
class TraceSpan:
    """A span within a request trace."""

    trace_id: str
    service: str
    start: str
    end: str
    entries: tuple[LogEntry, ...] = ()
    error: bool = False

    @property
    def entry_count(self) -> int:
        return len(self.entries)


@dataclass
class Trace:
    """A correlated trace across services."""

    trace_id: str
    spans: list[TraceSpan] = field(default_factory=list)

    @property
    def services(self) -> list[str]:
        return sorted({s.service for s in self.spans})

    @property
    def has_error(self) -> bool:
        return any(s.error for s in self.spans)

    @property
    def entry_count(self) -> int:
        return sum(s.entry_count for s in self.spans)


@dataclass
class TimelineEvent:
    """A single event on a timeline."""

    timestamp: str
    service: str
    level: str
    message: str
    trace_id: str = ""


@dataclass
class RootCauseChain:
    """Chain of events leading to a root cause."""

    root_entry: LogEntry
    chain: list[LogEntry] = field(default_factory=list)
    root_cause: str = ""

    @property
    def depth(self) -> int:
        return len(self.chain)


class LogCorrelator:
    """Correlate log entries across services for tracing and root-cause analysis."""

    def __init__(self, trace_field: str = "trace_id") -> None:
        self._trace_field = trace_field
        self._entries: list[LogEntry] = []

    def add_entries(self, entries: Sequence[LogEntry]) -> None:
        """Add parsed log entries for correlation."""
        self._entries = [*self._entries, *entries]

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def correlate(self) -> list[Trace]:
        """Group entries by trace ID and build traces."""
        groups: dict[str, list[LogEntry]] = {}
        for entry in self._entries:
            tid = entry.fields.get(self._trace_field, "")
            if not tid:
                continue
            groups.setdefault(tid, []).append(entry)

        traces: list[Trace] = []
        for tid, entries in sorted(groups.items()):
            spans = self._build_spans(tid, entries)
            traces.append(Trace(trace_id=tid, spans=spans))
        return traces

    def build_timeline(self, trace_id: str | None = None) -> list[TimelineEvent]:
        """Build a timeline of events, optionally filtered by trace ID."""
        source = self._entries
        if trace_id is not None:
            source = [
                e for e in self._entries
                if e.fields.get(self._trace_field) == trace_id
            ]

        events: list[TimelineEvent] = []
        for e in source:
            events.append(TimelineEvent(
                timestamp=e.timestamp,
                service=e.source,
                level=e.level,
                message=e.message,
                trace_id=e.fields.get(self._trace_field, ""),
            ))

        # Sort by timestamp string (ISO-sortable)
        return sorted(events, key=lambda ev: ev.timestamp)

    def find_root_cause(self, trace_id: str) -> RootCauseChain | None:
        """Find the root-cause chain for a given trace ID."""
        entries = [
            e for e in self._entries
            if e.fields.get(self._trace_field) == trace_id
        ]
        if not entries:
            return None

        sorted_entries = sorted(entries, key=lambda e: e.timestamp)
        error_entries = [e for e in sorted_entries if e.level in ("ERROR", "CRITICAL", "FATAL")]

        if not error_entries:
            return None

        root = error_entries[0]
        chain = sorted_entries[:sorted_entries.index(root) + 1]
        return RootCauseChain(
            root_entry=root,
            chain=chain,
            root_cause=root.message,
        )

    def service_map(self) -> dict[str, int]:
        """Return mapping of service name to entry count."""
        counts: dict[str, int] = {}
        for e in self._entries:
            svc = e.source or "unknown"
            counts[svc] = counts.get(svc, 0) + 1
        return dict(sorted(counts.items()))

    # -- Private -----------------------------------------------------------

    def _build_spans(self, tid: str, entries: list[LogEntry]) -> list[TraceSpan]:
        by_service: dict[str, list[LogEntry]] = {}
        for e in entries:
            svc = e.source or "unknown"
            by_service.setdefault(svc, []).append(e)

        spans: list[TraceSpan] = []
        for svc, svc_entries in sorted(by_service.items()):
            sorted_e = sorted(svc_entries, key=lambda x: x.timestamp)
            has_error = any(
                x.level in ("ERROR", "CRITICAL", "FATAL") for x in sorted_e
            )
            spans.append(TraceSpan(
                trace_id=tid,
                service=svc,
                start=sorted_e[0].timestamp if sorted_e else "",
                end=sorted_e[-1].timestamp if sorted_e else "",
                entries=tuple(sorted_e),
                error=has_error,
            ))
        return spans
