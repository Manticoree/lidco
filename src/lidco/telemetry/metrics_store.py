"""Q129 — Metrics & Telemetry: MetricsStore."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: float
    tags: dict = field(default_factory=dict)


class MetricsStore:
    """In-memory time-series store for numeric metrics."""

    def __init__(self) -> None:
        self._data: dict[str, list[MetricPoint]] = {}

    def record(self, name: str, value: float, tags: dict | None = None) -> MetricPoint:
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=dict(tags) if tags else {},
        )
        self._data.setdefault(name, []).append(point)
        return point

    def get_series(self, name: str) -> list[MetricPoint]:
        return list(self._data.get(name, []))

    def last(self, name: str) -> Optional[MetricPoint]:
        series = self._data.get(name, [])
        return series[-1] if series else None

    def aggregate(self, name: str, fn: str = "avg") -> float:
        series = self._data.get(name, [])
        if not series:
            return 0.0
        values = [p.value for p in series]
        if fn == "avg":
            return sum(values) / len(values)
        if fn == "sum":
            return sum(values)
        if fn == "min":
            return min(values)
        if fn == "max":
            return max(values)
        if fn == "count":
            return float(len(values))
        if fn == "last":
            return values[-1]
        raise ValueError(f"Unknown aggregation function: {fn!r}")

    def names(self) -> list[str]:
        return list(self._data.keys())

    def clear(self, name: str | None = None) -> None:
        if name is None:
            self._data.clear()
        else:
            self._data.pop(name, None)

    def __len__(self) -> int:
        return sum(len(v) for v in self._data.values())
