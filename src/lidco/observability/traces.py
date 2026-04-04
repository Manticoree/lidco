"""Q297 -- TraceCollector: OTel-like distributed tracing."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Span:
    """A single span within a trace."""

    span_id: str
    trace_id: str
    name: str
    parent_id: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "ok"
    attributes: dict[str, str] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.end_time <= 0:
            return 0.0
        return (self.end_time - self.start_time) * 1000


class TraceCollector:
    """Collect OpenTelemetry-style spans and build traces."""

    def __init__(self) -> None:
        self._spans: dict[str, Span] = {}
        self._traces: dict[str, list[str]] = {}

    # -- span lifecycle ----------------------------------------------------

    def start_span(self, name: str, parent: Optional[str] = None) -> Span:
        """Start a new span.  If *parent* is a span_id, inherit its trace_id."""
        span_id = uuid.uuid4().hex[:16]
        if parent and parent in self._spans:
            trace_id = self._spans[parent].trace_id
        else:
            trace_id = uuid.uuid4().hex[:16]

        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            parent_id=parent,
            start_time=time.time(),
        )
        self._spans[span_id] = span
        self._traces.setdefault(trace_id, []).append(span_id)
        return span

    def end_span(self, span_id: str) -> Span:
        """End a span, recording end_time.  Returns the span."""
        span = self._spans.get(span_id)
        if span is None:
            raise KeyError(f"Unknown span_id: {span_id}")
        span.end_time = time.time()
        return span

    # -- queries -----------------------------------------------------------

    def get_trace(self, trace_id: str) -> list[Span]:
        """Return all spans for a trace, ordered by start_time."""
        span_ids = self._traces.get(trace_id, [])
        spans = [self._spans[sid] for sid in span_ids if sid in self._spans]
        spans.sort(key=lambda s: s.start_time)
        return spans

    def latency_breakdown(self, trace_id: str) -> dict[str, float]:
        """Return span name -> duration_ms mapping for a trace."""
        spans = self.get_trace(trace_id)
        return {s.name: s.duration_ms for s in spans}

    def service_map(self) -> dict[str, list[str]]:
        """Build a service map: parent span name -> list of child span names."""
        result: dict[str, list[str]] = {}
        for span in self._spans.values():
            if span.parent_id and span.parent_id in self._spans:
                parent_name = self._spans[span.parent_id].name
                result.setdefault(parent_name, [])
                if span.name not in result[parent_name]:
                    result[parent_name].append(span.name)
        return result
