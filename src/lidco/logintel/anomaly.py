"""Log Anomaly Detector — detect unusual patterns, volume spikes, and new error types.

Uses seasonal baseline comparison for anomaly scoring.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

from lidco.logintel.parser import LogEntry


class AnomalyType(Enum):
    """Types of log anomalies."""

    VOLUME_SPIKE = "volume_spike"
    NEW_ERROR = "new_error"
    UNUSUAL_PATTERN = "unusual_pattern"
    LEVEL_SHIFT = "level_shift"
    MISSING_SERVICE = "missing_service"


@dataclass(frozen=True)
class Anomaly:
    """A detected anomaly."""

    anomaly_type: AnomalyType
    description: str
    score: float  # 0.0–1.0, higher = more anomalous
    entries: tuple[LogEntry, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Baseline:
    """Seasonal baseline for comparison."""

    avg_volume: float = 0.0
    std_volume: float = 0.0
    known_errors: set[str] = field(default_factory=set)
    level_distribution: dict[str, float] = field(default_factory=dict)
    known_services: set[str] = field(default_factory=set)

    @property
    def is_empty(self) -> bool:
        return self.avg_volume == 0.0 and not self.known_errors


@dataclass
class AnomalyReport:
    """Report of detected anomalies."""

    anomalies: list[Anomaly] = field(default_factory=list)
    total_entries: int = 0
    baseline_used: bool = False

    @property
    def count(self) -> int:
        return len(self.anomalies)

    @property
    def max_score(self) -> float:
        if not self.anomalies:
            return 0.0
        return max(a.score for a in self.anomalies)

    def by_type(self, atype: AnomalyType) -> list[Anomaly]:
        return [a for a in self.anomalies if a.anomaly_type == atype]


class LogAnomalyDetector:
    """Detect anomalies in log entries against a baseline."""

    def __init__(self, volume_threshold: float = 2.0, score_threshold: float = 0.3) -> None:
        self._volume_threshold = volume_threshold
        self._score_threshold = score_threshold
        self._baseline: Baseline = Baseline()

    @property
    def baseline(self) -> Baseline:
        return self._baseline

    def set_baseline(self, baseline: Baseline) -> None:
        """Set the baseline for comparison."""
        self._baseline = baseline

    def build_baseline(self, entries: Sequence[LogEntry]) -> Baseline:
        """Build a baseline from historical log entries."""
        if not entries:
            return Baseline()

        # Volume
        avg = float(len(entries))
        # Level distribution
        level_counts: dict[str, int] = {}
        services: set[str] = set()
        errors: set[str] = set()

        for e in entries:
            lv = e.level or "UNKNOWN"
            level_counts[lv] = level_counts.get(lv, 0) + 1
            if e.source:
                services.add(e.source)
            if lv in ("ERROR", "CRITICAL", "FATAL"):
                errors.add(e.message)

        total = float(len(entries)) or 1.0
        level_dist = {k: v / total for k, v in level_counts.items()}

        return Baseline(
            avg_volume=avg,
            std_volume=math.sqrt(avg),  # Poisson-like approximation
            known_errors=errors,
            level_distribution=level_dist,
            known_services=services,
        )

    def detect(self, entries: Sequence[LogEntry]) -> AnomalyReport:
        """Detect anomalies in the given entries against the current baseline."""
        report = AnomalyReport(total_entries=len(entries), baseline_used=not self._baseline.is_empty)
        anomalies: list[Anomaly] = []

        anomalies.extend(self._check_volume_spike(entries))
        anomalies.extend(self._check_new_errors(entries))
        anomalies.extend(self._check_level_shift(entries))
        anomalies.extend(self._check_missing_services(entries))

        # Filter by threshold
        report.anomalies = [a for a in anomalies if a.score >= self._score_threshold]
        return report

    # -- Private checks ----------------------------------------------------

    def _check_volume_spike(self, entries: Sequence[LogEntry]) -> list[Anomaly]:
        if self._baseline.is_empty or self._baseline.std_volume == 0:
            return []
        volume = float(len(entries))
        z = (volume - self._baseline.avg_volume) / self._baseline.std_volume
        if z > self._volume_threshold:
            score = min(1.0, z / (self._volume_threshold * 3))
            return [Anomaly(
                anomaly_type=AnomalyType.VOLUME_SPIKE,
                description=f"Volume spike: {len(entries)} entries (baseline avg {self._baseline.avg_volume:.0f})",
                score=score,
                metadata={"z_score": z, "volume": len(entries), "baseline_avg": self._baseline.avg_volume},
            )]
        return []

    def _check_new_errors(self, entries: Sequence[LogEntry]) -> list[Anomaly]:
        results: list[Anomaly] = []
        for e in entries:
            if e.level in ("ERROR", "CRITICAL", "FATAL"):
                if e.message and e.message not in self._baseline.known_errors:
                    results.append(Anomaly(
                        anomaly_type=AnomalyType.NEW_ERROR,
                        description=f"New error type: {e.message[:120]}",
                        score=0.8,
                        entries=(e,),
                        metadata={"level": e.level},
                    ))
        # Deduplicate by message
        seen: set[str] = set()
        deduped: list[Anomaly] = []
        for a in results:
            key = a.description
            if key not in seen:
                seen.add(key)
                deduped.append(a)
        return deduped

    def _check_level_shift(self, entries: Sequence[LogEntry]) -> list[Anomaly]:
        if not self._baseline.level_distribution:
            return []

        level_counts: dict[str, int] = {}
        for e in entries:
            lv = e.level or "UNKNOWN"
            level_counts[lv] = level_counts.get(lv, 0) + 1

        total = float(len(entries)) or 1.0
        current_dist = {k: v / total for k, v in level_counts.items()}

        results: list[Anomaly] = []
        for level in ("ERROR", "CRITICAL", "FATAL"):
            baseline_pct = self._baseline.level_distribution.get(level, 0.0)
            current_pct = current_dist.get(level, 0.0)
            if current_pct > baseline_pct + 0.1:
                score = min(1.0, (current_pct - baseline_pct) * 2)
                results.append(Anomaly(
                    anomaly_type=AnomalyType.LEVEL_SHIFT,
                    description=f"{level} rate shifted from {baseline_pct:.0%} to {current_pct:.0%}",
                    score=score,
                    metadata={"level": level, "baseline_pct": baseline_pct, "current_pct": current_pct},
                ))
        return results

    def _check_missing_services(self, entries: Sequence[LogEntry]) -> list[Anomaly]:
        if not self._baseline.known_services:
            return []

        current_services = {e.source for e in entries if e.source}
        missing = self._baseline.known_services - current_services

        results: list[Anomaly] = []
        for svc in sorted(missing):
            results.append(Anomaly(
                anomaly_type=AnomalyType.MISSING_SERVICE,
                description=f"Service '{svc}' missing from current logs",
                score=0.6,
                metadata={"service": svc},
            ))
        return results
