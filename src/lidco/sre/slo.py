"""SLO Tracker — define SLOs, track error budgets, burn rate alerts, SLI measurement, reporting.

Stdlib only.  No external dependencies.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class SLOError(Exception):
    """Raised when an SLO operation fails."""


class BurnRateSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SLI:
    """A single Service Level Indicator measurement."""

    name: str
    value: float
    good: bool
    timestamp: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class SLO:
    """Service Level Objective definition."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    target: float = 0.999  # 99.9%
    window_seconds: float = 30 * 24 * 3600  # 30 days
    sli_name: str = ""

    def error_budget_fraction(self) -> float:
        """Return the fraction of requests allowed to fail (1 - target)."""
        return 1.0 - self.target

    def error_budget_minutes(self) -> float:
        """Return the error budget expressed in minutes."""
        return (self.window_seconds / 60.0) * self.error_budget_fraction()


@dataclass
class BurnRateAlert:
    """Alert definition based on error budget burn rate."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    slo_id: str = ""
    threshold: float = 1.0  # burn rate multiplier
    severity: BurnRateSeverity = BurnRateSeverity.MEDIUM
    short_window_seconds: float = 3600  # 1h
    long_window_seconds: float = 6 * 3600  # 6h
    notification_channel: str = ""


@dataclass
class BudgetStatus:
    """Snapshot of an SLO's error budget consumption."""

    slo_id: str
    slo_name: str
    target: float
    total_events: int
    bad_events: int
    budget_total: float
    budget_remaining: float
    budget_consumed_fraction: float
    burn_rate: float
    is_healthy: bool


@dataclass
class SLOReport:
    """Generated report for one or more SLOs."""

    generated_at: float = field(default_factory=time.time)
    statuses: list[BudgetStatus] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"SLO Report ({len(self.statuses)} SLOs):"]
        for s in self.statuses:
            health = "HEALTHY" if s.is_healthy else "AT RISK"
            pct = s.budget_consumed_fraction * 100
            lines.append(
                f"  {s.slo_name}: {health} — "
                f"budget consumed {pct:.1f}%, burn rate {s.burn_rate:.2f}x"
            )
        return "\n".join(lines)


class SLOTracker:
    """Track SLOs, record SLIs, compute budgets and burn rates."""

    def __init__(self) -> None:
        self._slos: dict[str, SLO] = {}
        self._alerts: dict[str, BurnRateAlert] = {}
        self._measurements: list[SLI] = []
        self._alert_callbacks: list[Callable[[BurnRateAlert, BudgetStatus], Any]] = []

    # ---- SLO management ----

    def define_slo(self, slo: SLO) -> SLO:
        """Register an SLO definition."""
        if not slo.name:
            raise SLOError("SLO name is required")
        if not 0 < slo.target < 1:
            raise SLOError(f"Target must be between 0 and 1, got {slo.target}")
        self._slos[slo.id] = slo
        return slo

    def get_slo(self, slo_id: str) -> SLO:
        if slo_id not in self._slos:
            raise SLOError(f"SLO not found: {slo_id}")
        return self._slos[slo_id]

    def list_slos(self) -> list[SLO]:
        return list(self._slos.values())

    def remove_slo(self, slo_id: str) -> None:
        if slo_id not in self._slos:
            raise SLOError(f"SLO not found: {slo_id}")
        del self._slos[slo_id]

    # ---- SLI recording ----

    def record_sli(self, sli: SLI) -> None:
        """Record a Service Level Indicator measurement."""
        self._measurements.append(sli)
        self._check_alerts(sli.name)

    def record_event(self, sli_name: str, good: bool, labels: dict[str, str] | None = None) -> SLI:
        """Convenience: record a single good/bad event."""
        sli = SLI(name=sli_name, value=1.0 if good else 0.0, good=good, labels=labels or {})
        self.record_sli(sli)
        return sli

    def get_measurements(self, sli_name: str | None = None, since: float | None = None) -> list[SLI]:
        result = self._measurements
        if sli_name is not None:
            result = [m for m in result if m.name == sli_name]
        if since is not None:
            result = [m for m in result if m.timestamp >= since]
        return result

    # ---- Budget computation ----

    def budget_status(self, slo_id: str) -> BudgetStatus:
        """Compute current error budget status for an SLO."""
        slo = self.get_slo(slo_id)
        cutoff = time.time() - slo.window_seconds
        events = [m for m in self._measurements if m.name == slo.sli_name and m.timestamp >= cutoff]
        total = len(events)
        bad = sum(1 for e in events if not e.good)

        budget_total = max(total * slo.error_budget_fraction(), 1.0)
        budget_remaining = max(budget_total - bad, 0.0)
        consumed = bad / budget_total if budget_total > 0 else 0.0

        # burn rate: how fast we're consuming budget relative to expected
        expected_fraction = 1.0  # over the full window we expect to consume at most 1x
        burn_rate = consumed / expected_fraction if expected_fraction > 0 else 0.0

        return BudgetStatus(
            slo_id=slo.id,
            slo_name=slo.name,
            target=slo.target,
            total_events=total,
            bad_events=bad,
            budget_total=budget_total,
            budget_remaining=budget_remaining,
            budget_consumed_fraction=consumed,
            burn_rate=burn_rate,
            is_healthy=consumed < 1.0,
        )

    # ---- Alerts ----

    def add_alert(self, alert: BurnRateAlert) -> BurnRateAlert:
        if alert.slo_id not in self._slos:
            raise SLOError(f"SLO not found: {alert.slo_id}")
        self._alerts[alert.id] = alert
        return alert

    def remove_alert(self, alert_id: str) -> None:
        if alert_id not in self._alerts:
            raise SLOError(f"Alert not found: {alert_id}")
        del self._alerts[alert_id]

    def list_alerts(self) -> list[BurnRateAlert]:
        return list(self._alerts.values())

    def on_alert(self, callback: Callable[[BurnRateAlert, BudgetStatus], Any]) -> None:
        """Register a callback for burn rate alert firings."""
        self._alert_callbacks.append(callback)

    def _check_alerts(self, sli_name: str) -> None:
        for alert in self._alerts.values():
            slo = self._slos.get(alert.slo_id)
            if slo is None or slo.sli_name != sli_name:
                continue
            status = self.budget_status(alert.slo_id)
            if status.burn_rate >= alert.threshold:
                for cb in self._alert_callbacks:
                    cb(alert, status)

    # ---- Reporting ----

    def report(self, slo_ids: list[str] | None = None) -> SLOReport:
        """Generate a report for the given SLOs (or all)."""
        ids = slo_ids or list(self._slos.keys())
        statuses = [self.budget_status(sid) for sid in ids]
        return SLOReport(statuses=statuses)
