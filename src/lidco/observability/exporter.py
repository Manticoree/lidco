"""Q297 -- MetricsExporter: record, counter, histogram, export."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricPoint:
    """Single metric data point."""

    name: str
    value: float
    labels: dict[str, str]
    timestamp: float


class MetricsExporter:
    """Collects and exports metrics in Prometheus and JSON formats."""

    def __init__(self) -> None:
        self._points: list[MetricPoint] = []
        self._counters: dict[str, int] = {}
        self._histograms: dict[str, list[float]] = {}

    # -- recording ---------------------------------------------------------

    def record(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a metric data point."""
        point = MetricPoint(
            name=name,
            value=value,
            labels=labels or {},
            timestamp=time.time(),
        )
        self._points.append(point)

    def counter(self, name: str) -> int:
        """Increment and return counter value for *name*."""
        self._counters[name] = self._counters.get(name, 0) + 1
        return self._counters[name]

    def histogram(self, name: str, value: float) -> None:
        """Add *value* to histogram bucket for *name*."""
        self._histograms.setdefault(name, []).append(value)

    # -- export ------------------------------------------------------------

    def export_prometheus(self) -> str:
        """Render metrics in Prometheus text exposition format."""
        lines: list[str] = []
        # counters
        for name, val in sorted(self._counters.items()):
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {val}")
        # histograms as summary lines
        for name, vals in sorted(self._histograms.items()):
            lines.append(f"# TYPE {name} histogram")
            lines.append(f"{name}_count {len(vals)}")
            lines.append(f"{name}_sum {sum(vals)}")
        # raw points
        for pt in self._points:
            label_str = ""
            if pt.labels:
                pairs = ",".join(f'{k}="{v}"' for k, v in sorted(pt.labels.items()))
                label_str = "{" + pairs + "}"
            lines.append(f"{pt.name}{label_str} {pt.value}")
        return "\n".join(lines)

    def export_json(self) -> dict[str, Any]:
        """Export all metrics as a JSON-serialisable dict."""
        return {
            "counters": dict(self._counters),
            "histograms": {
                name: {
                    "count": len(vals),
                    "sum": sum(vals),
                    "min": min(vals) if vals else 0,
                    "max": max(vals) if vals else 0,
                }
                for name, vals in self._histograms.items()
            },
            "points": [
                {"name": p.name, "value": p.value, "labels": p.labels}
                for p in self._points
            ],
        }

    def summary(self) -> dict[str, Any]:
        """High-level summary of collected metrics."""
        return {
            "total_points": len(self._points),
            "counter_names": sorted(self._counters.keys()),
            "histogram_names": sorted(self._histograms.keys()),
            "counters": len(self._counters),
            "histograms": len(self._histograms),
        }
