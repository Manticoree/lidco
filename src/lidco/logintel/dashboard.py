"""Log Dashboard — visualization, timeline, volume chart, error rate, top errors.

Provides export and drill-down capabilities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Sequence

from lidco.logintel.parser import LogEntry


@dataclass
class VolumePoint:
    """A single point on a volume chart."""

    bucket: str
    count: int
    error_count: int = 0

    @property
    def error_rate(self) -> float:
        if self.count == 0:
            return 0.0
        return self.error_count / self.count


@dataclass
class TopError:
    """A frequently occurring error."""

    message: str
    count: int
    level: str = "ERROR"
    first_seen: str = ""
    last_seen: str = ""


@dataclass
class ServiceSummary:
    """Summary for one service."""

    service: str
    total: int
    error_count: int
    warn_count: int

    @property
    def error_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.error_count / self.total


@dataclass
class DashboardData:
    """Complete dashboard data structure."""

    total_entries: int = 0
    error_count: int = 0
    warn_count: int = 0
    volume_chart: list[VolumePoint] = field(default_factory=list)
    top_errors: list[TopError] = field(default_factory=list)
    services: list[ServiceSummary] = field(default_factory=list)
    timeline_start: str = ""
    timeline_end: str = ""

    @property
    def error_rate(self) -> float:
        if self.total_entries == 0:
            return 0.0
        return self.error_count / self.total_entries


class LogDashboard:
    """Build dashboard data from parsed log entries."""

    def __init__(self, top_n: int = 10, bucket_size: str = "hour") -> None:
        self._top_n = top_n
        self._bucket_size = bucket_size

    def build(self, entries: Sequence[LogEntry]) -> DashboardData:
        """Build dashboard data from log entries."""
        if not entries:
            return DashboardData()

        data = DashboardData(total_entries=len(entries))

        error_levels = {"ERROR", "CRITICAL", "FATAL"}
        warn_levels = {"WARN", "WARNING"}

        error_msgs: dict[str, list[LogEntry]] = {}

        for e in entries:
            if e.level in error_levels:
                data.error_count += 1
                error_msgs.setdefault(e.message, []).append(e)
            elif e.level in warn_levels:
                data.warn_count += 1

        # Top errors
        sorted_errors = sorted(error_msgs.items(), key=lambda x: len(x[1]), reverse=True)
        for msg, err_entries in sorted_errors[: self._top_n]:
            timestamps = [x.timestamp for x in err_entries if x.timestamp]
            data.top_errors.append(TopError(
                message=msg,
                count=len(err_entries),
                level=err_entries[0].level,
                first_seen=min(timestamps) if timestamps else "",
                last_seen=max(timestamps) if timestamps else "",
            ))

        # Volume chart by bucket
        data.volume_chart = self._build_volume_chart(entries)

        # Services
        data.services = self._build_service_summaries(entries)

        # Timeline range
        timestamps = sorted(e.timestamp for e in entries if e.timestamp)
        if timestamps:
            data.timeline_start = timestamps[0]
            data.timeline_end = timestamps[-1]

        return data

    def drill_down(self, entries: Sequence[LogEntry], service: str | None = None,
                   level: str | None = None) -> list[LogEntry]:
        """Filter entries for drill-down."""
        result: list[LogEntry] = []
        for e in entries:
            if service is not None and e.source != service:
                continue
            if level is not None and e.level != level.upper():
                continue
            result.append(e)
        return result

    def export_json(self, data: DashboardData) -> str:
        """Export dashboard data as JSON."""
        payload: dict[str, Any] = {
            "total_entries": data.total_entries,
            "error_count": data.error_count,
            "warn_count": data.warn_count,
            "error_rate": round(data.error_rate, 4),
            "timeline_start": data.timeline_start,
            "timeline_end": data.timeline_end,
            "volume_chart": [
                {"bucket": v.bucket, "count": v.count, "error_count": v.error_count}
                for v in data.volume_chart
            ],
            "top_errors": [
                {"message": t.message, "count": t.count, "level": t.level}
                for t in data.top_errors
            ],
            "services": [
                {"service": s.service, "total": s.total, "error_count": s.error_count,
                 "error_rate": round(s.error_rate, 4)}
                for s in data.services
            ],
        }
        return json.dumps(payload, indent=2)

    def export_text(self, data: DashboardData) -> str:
        """Export dashboard data as plain text."""
        lines: list[str] = []
        lines.append(f"Log Dashboard ({data.total_entries} entries)")
        lines.append(f"  Errors: {data.error_count}  Warnings: {data.warn_count}  "
                      f"Error rate: {data.error_rate:.1%}")
        if data.timeline_start:
            lines.append(f"  Range: {data.timeline_start} — {data.timeline_end}")

        if data.top_errors:
            lines.append("")
            lines.append("Top Errors:")
            for te in data.top_errors:
                lines.append(f"  [{te.count}x] {te.message[:100]}")

        if data.services:
            lines.append("")
            lines.append("Services:")
            for s in data.services:
                lines.append(f"  {s.service}: {s.total} entries, {s.error_count} errors "
                              f"({s.error_rate:.1%})")
        return "\n".join(lines)

    # -- Private -----------------------------------------------------------

    def _build_volume_chart(self, entries: Sequence[LogEntry]) -> list[VolumePoint]:
        buckets: dict[str, list[LogEntry]] = {}
        error_levels = {"ERROR", "CRITICAL", "FATAL"}

        for e in entries:
            bk = self._bucket_key(e.timestamp)
            buckets.setdefault(bk, []).append(e)

        points: list[VolumePoint] = []
        for bk in sorted(buckets.keys()):
            group = buckets[bk]
            ec = sum(1 for x in group if x.level in error_levels)
            points.append(VolumePoint(bucket=bk, count=len(group), error_count=ec))
        return points

    def _bucket_key(self, timestamp: str) -> str:
        if not timestamp:
            return "unknown"
        # Try to bucket by hour: take first 13 chars of ISO timestamp (YYYY-MM-DDTHH)
        if len(timestamp) >= 13 and "T" in timestamp:
            return timestamp[:13]
        # Fallback: first 10 chars (date)
        if len(timestamp) >= 10:
            return timestamp[:10]
        return timestamp

    def _build_service_summaries(self, entries: Sequence[LogEntry]) -> list[ServiceSummary]:
        svc_data: dict[str, dict[str, int]] = {}
        error_levels = {"ERROR", "CRITICAL", "FATAL"}
        warn_levels = {"WARN", "WARNING"}

        for e in entries:
            svc = e.source or "unknown"
            d = svc_data.setdefault(svc, {"total": 0, "error": 0, "warn": 0})
            d["total"] += 1
            if e.level in error_levels:
                d["error"] += 1
            elif e.level in warn_levels:
                d["warn"] += 1

        return [
            ServiceSummary(service=svc, total=d["total"],
                           error_count=d["error"], warn_count=d["warn"])
            for svc, d in sorted(svc_data.items())
        ]
