"""Traffic Analyzer — service-to-service traffic, request volume, latency, error rates, patterns."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence


class TrafficPattern(Enum):
    """Recognised traffic patterns."""

    STEADY = "steady"
    BURSTY = "bursty"
    GROWING = "growing"
    DECLINING = "declining"
    PERIODIC = "periodic"


@dataclass(frozen=True)
class TrafficRecord:
    """A single traffic observation between two services."""

    source: str
    target: str
    timestamp: float
    latency_ms: float
    status_code: int = 200
    request_size_bytes: int = 0
    response_size_bytes: int = 0


@dataclass(frozen=True)
class PairSummary:
    """Aggregated stats for a source->target pair."""

    source: str
    target: str
    total_requests: int
    avg_latency_ms: float
    p50_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    pattern: TrafficPattern


@dataclass(frozen=True)
class TrafficReport:
    """Full traffic analysis report."""

    total_records: int
    pairs: tuple[PairSummary, ...]
    top_talkers: tuple[str, ...]
    hotspots: tuple[str, ...]


class TrafficAnalyzer:
    """Analyze service-to-service traffic."""

    def __init__(self, records: Sequence[TrafficRecord] | None = None) -> None:
        self._records: list[TrafficRecord] = list(records or [])

    def add_record(self, record: TrafficRecord) -> None:
        """Append a traffic record."""
        self._records.append(record)

    def add_records(self, records: Sequence[TrafficRecord]) -> None:
        """Append multiple traffic records."""
        self._records.extend(records)

    @property
    def record_count(self) -> int:
        return len(self._records)

    # -- analysis helpers --

    def _group_by_pair(self) -> dict[tuple[str, str], list[TrafficRecord]]:
        groups: dict[tuple[str, str], list[TrafficRecord]] = {}
        for r in self._records:
            key = (r.source, r.target)
            groups.setdefault(key, []).append(r)
        return groups

    @staticmethod
    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * (pct / 100.0)
        f = int(k)
        c = f + 1
        if c >= len(sorted_vals):
            return sorted_vals[f]
        return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])

    @staticmethod
    def _detect_pattern(records: list[TrafficRecord]) -> TrafficPattern:
        if len(records) < 3:
            return TrafficPattern.STEADY
        timestamps = sorted(r.timestamp for r in records)
        gaps = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        if not gaps:
            return TrafficPattern.STEADY
        mean_gap = statistics.mean(gaps)
        if mean_gap == 0:
            return TrafficPattern.BURSTY
        stdev_gap = statistics.pstdev(gaps)
        cv = stdev_gap / mean_gap if mean_gap else 0
        if cv > 1.0:
            return TrafficPattern.BURSTY
        # simple trend: compare first-half vs second-half counts by time midpoint
        time_mid = (timestamps[0] + timestamps[-1]) / 2.0
        first_half = sum(1 for t in timestamps if t < time_mid)
        second_half = sum(1 for t in timestamps if t > time_mid)
        if second_half > first_half * 1.3:
            return TrafficPattern.GROWING
        if first_half > second_half * 1.3:
            return TrafficPattern.DECLINING
        return TrafficPattern.STEADY

    def _summarize_pair(self, source: str, target: str,
                        records: list[TrafficRecord]) -> PairSummary:
        latencies = [r.latency_ms for r in records]
        errors = sum(1 for r in records if r.status_code >= 400)
        error_rate = errors / len(records) if records else 0.0
        return PairSummary(
            source=source,
            target=target,
            total_requests=len(records),
            avg_latency_ms=round(statistics.mean(latencies), 2) if latencies else 0.0,
            p50_latency_ms=round(self._percentile(latencies, 50), 2),
            p99_latency_ms=round(self._percentile(latencies, 99), 2),
            error_rate=round(error_rate, 4),
            pattern=self._detect_pattern(records),
        )

    # -- public API --

    def analyze(self) -> TrafficReport:
        """Produce a full traffic report."""
        groups = self._group_by_pair()
        pairs: list[PairSummary] = []
        for (src, tgt), recs in groups.items():
            pairs.append(self._summarize_pair(src, tgt, recs))

        # top talkers: services with most outgoing requests
        talker_counts: dict[str, int] = {}
        for p in pairs:
            talker_counts[p.source] = talker_counts.get(p.source, 0) + p.total_requests
        top_talkers = tuple(
            k for k, _ in sorted(talker_counts.items(), key=lambda x: -x[1])
        )

        # hotspots: pairs with high error rate or high latency
        hotspots: list[str] = []
        for p in pairs:
            if p.error_rate > 0.05 or p.p99_latency_ms > 1000:
                hotspots.append(f"{p.source}->{p.target}")

        return TrafficReport(
            total_records=len(self._records),
            pairs=tuple(sorted(pairs, key=lambda p: -p.total_requests)),
            top_talkers=top_talkers,
            hotspots=tuple(hotspots),
        )

    def volume_for(self, source: str, target: str) -> int:
        """Return request count for a specific pair."""
        return sum(1 for r in self._records
                   if r.source == source and r.target == target)

    def error_rate_for(self, source: str, target: str) -> float:
        """Return error rate for a specific pair."""
        recs = [r for r in self._records
                if r.source == source and r.target == target]
        if not recs:
            return 0.0
        return sum(1 for r in recs if r.status_code >= 400) / len(recs)
