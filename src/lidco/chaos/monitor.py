"""
Chaos Monitor — monitor system during chaos experiments.

Tracks health metrics, recovery time, error rates, and SLA impact.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HealthStatus(Enum):
    """System health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HealthMetric:
    """A single health metric sample."""

    name: str
    value: float
    timestamp: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class ErrorRateWindow:
    """Error rate in a time window."""

    window_seconds: float
    total_requests: int
    error_count: int

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests


@dataclass
class SLAReport:
    """SLA impact report."""

    target_availability: float
    actual_availability: float
    total_downtime_seconds: float
    violations: list[dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.violations, dict):
            self.violations = []

    @property
    def is_within_sla(self) -> bool:
        return self.actual_availability >= self.target_availability


@dataclass
class RecoveryReport:
    """Recovery time report."""

    experiment_id: str
    failure_detected_at: float
    recovery_detected_at: float
    recovery_time_seconds: float
    full_recovery: bool


class ChaosMonitor:
    """Monitor system health during chaos experiments."""

    def __init__(self, *, sla_target: float = 0.999) -> None:
        self._metrics: list[HealthMetric] = []
        self._error_events: list[dict[str, Any]] = []
        self._recovery_reports: list[RecoveryReport] = []
        self._health_status: HealthStatus = HealthStatus.HEALTHY
        self._sla_target: float = sla_target
        self._downtime_periods: list[tuple[float, float]] = []
        self._monitoring_start: float = time.time()

    def record_metric(
        self,
        name: str,
        value: float,
        *,
        tags: dict[str, str] | None = None,
    ) -> HealthMetric:
        """Record a health metric sample."""
        metric = HealthMetric(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags or {},
        )
        self._metrics = [*self._metrics, metric]
        return metric

    def record_error(
        self,
        error_type: str,
        *,
        target: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record an error event."""
        event = {
            "error_type": error_type,
            "target": target,
            "timestamp": time.time(),
            "details": details or {},
        }
        self._error_events = [*self._error_events, event]

    def set_health_status(self, status: HealthStatus) -> None:
        """Update the current system health status."""
        if (
            self._health_status == HealthStatus.HEALTHY
            and status != HealthStatus.HEALTHY
        ):
            self._downtime_periods = [
                *self._downtime_periods,
                (time.time(), 0.0),
            ]
        elif (
            self._health_status != HealthStatus.HEALTHY
            and status == HealthStatus.HEALTHY
            and self._downtime_periods
        ):
            last_start, _ = self._downtime_periods[-1]
            self._downtime_periods = [
                *self._downtime_periods[:-1],
                (last_start, time.time()),
            ]
        self._health_status = status

    @property
    def health_status(self) -> HealthStatus:
        return self._health_status

    def get_error_rate(self, window_seconds: float = 60.0) -> ErrorRateWindow:
        """Get error rate in the specified time window."""
        cutoff = time.time() - window_seconds
        recent_errors = [
            e for e in self._error_events if e["timestamp"] >= cutoff
        ]
        recent_metrics = [
            m for m in self._metrics if m.timestamp >= cutoff
        ]
        total = len(recent_metrics) + len(recent_errors)
        return ErrorRateWindow(
            window_seconds=window_seconds,
            total_requests=total,
            error_count=len(recent_errors),
        )

    def record_recovery(
        self,
        experiment_id: str,
        *,
        failure_at: float,
        recovery_at: float,
        full_recovery: bool = True,
    ) -> RecoveryReport:
        """Record a recovery event."""
        report = RecoveryReport(
            experiment_id=experiment_id,
            failure_detected_at=failure_at,
            recovery_detected_at=recovery_at,
            recovery_time_seconds=recovery_at - failure_at,
            full_recovery=full_recovery,
        )
        self._recovery_reports = [*self._recovery_reports, report]
        return report

    def get_sla_report(self) -> SLAReport:
        """Generate an SLA impact report."""
        now = time.time()
        total_time = now - self._monitoring_start
        if total_time <= 0:
            return SLAReport(
                target_availability=self._sla_target,
                actual_availability=1.0,
                total_downtime_seconds=0.0,
                violations=[],
            )

        total_downtime = 0.0
        violations: list[dict[str, Any]] = []
        for start, end in self._downtime_periods:
            end_time = end if end > 0 else now
            duration = end_time - start
            total_downtime += duration
            violations.append(
                {"start": start, "end": end_time, "duration": duration}
            )

        actual = 1.0 - (total_downtime / total_time) if total_time > 0 else 1.0
        return SLAReport(
            target_availability=self._sla_target,
            actual_availability=actual,
            total_downtime_seconds=total_downtime,
            violations=violations if actual < self._sla_target else [],
        )

    def get_metrics(
        self,
        *,
        name: str | None = None,
        since: float | None = None,
    ) -> list[HealthMetric]:
        """Get recorded metrics, optionally filtered."""
        result = list(self._metrics)
        if name is not None:
            result = [m for m in result if m.name == name]
        if since is not None:
            result = [m for m in result if m.timestamp >= since]
        return result

    @property
    def recovery_reports(self) -> list[RecoveryReport]:
        return list(self._recovery_reports)

    @property
    def error_count(self) -> int:
        return len(self._error_events)

    def summary(self) -> dict[str, Any]:
        """Return a summary of monitoring data."""
        sla = self.get_sla_report()
        return {
            "health_status": self._health_status.value,
            "total_metrics": len(self._metrics),
            "total_errors": len(self._error_events),
            "recoveries": len(self._recovery_reports),
            "sla_target": self._sla_target,
            "actual_availability": sla.actual_availability,
            "within_sla": sla.is_within_sla,
            "total_downtime_seconds": sla.total_downtime_seconds,
        }
