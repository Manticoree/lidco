"""AuditDashboard — Real-time audit view, event stream, and risk score."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from lidco.audit.anomaly import Anomaly, AnomalyDetector
from lidco.audit.event_store import AuditEvent, AuditEventStore


_SEVERITY_WEIGHT = {"low": 1, "medium": 3, "high": 7, "critical": 15}


@dataclass(frozen=True)
class DashboardMetrics:
    """Snapshot of audit dashboard metrics."""

    total_events: int
    active_actors: int
    risk_score: float
    top_actors: list[tuple[str, int]]
    top_actions: list[tuple[str, int]]
    anomaly_count: int
    recent_events: list[AuditEvent]


class AuditDashboard:
    """Real-time audit dashboard with risk scoring.

    Parameters
    ----------
    store:
        The :class:`AuditEventStore` backing this dashboard.
    detector:
        Optional :class:`AnomalyDetector` for risk computation.
    """

    def __init__(self, store: AuditEventStore, detector: AnomalyDetector | None = None) -> None:
        self._store = store
        self._detector = detector

    # ---------------------------------------------------------------- risk

    def risk_score(self) -> float:
        """Compute risk score 0-100 based on anomaly count and severity."""
        if self._detector is None:
            return 0.0
        anomalies = self._detector.anomalies()
        if not anomalies:
            return 0.0
        total_weight = sum(_SEVERITY_WEIGHT.get(a.severity, 1) for a in anomalies)
        # Clamp to 100
        score = min(total_weight * 5.0, 100.0)
        return round(score, 1)

    # ---------------------------------------------------------------- recent

    def recent(self, limit: int = 20) -> list[AuditEvent]:
        """Return the most recent events."""
        events = self._store.events()
        return events[-limit:] if len(events) > limit else list(events)

    # ---------------------------------------------------------------- metrics

    def metrics(self) -> DashboardMetrics:
        """Compute full dashboard metrics snapshot."""
        events = self._store.events()

        actor_counts: dict[str, int] = defaultdict(int)
        action_counts: dict[str, int] = defaultdict(int)
        for e in events:
            actor_counts[e.actor] += 1
            action_counts[e.action] += 1

        top_actors = sorted(actor_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        anomaly_count = len(self._detector.anomalies()) if self._detector else 0

        return DashboardMetrics(
            total_events=len(events),
            active_actors=len(actor_counts),
            risk_score=self.risk_score(),
            top_actors=top_actors,
            top_actions=top_actions,
            anomaly_count=anomaly_count,
            recent_events=events[-20:] if len(events) > 20 else list(events),
        )

    # ---------------------------------------------------------------- actor

    def actor_activity(self, actor: str) -> dict[str, Any]:
        """Return activity summary for a single actor."""
        events = self._store.events()
        actor_events = [e for e in events if e.actor == actor]
        action_counts: dict[str, int] = defaultdict(int)
        for e in actor_events:
            action_counts[e.action] += 1

        top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        last_active = actor_events[-1].timestamp if actor_events else 0.0

        return {
            "actor": actor,
            "event_count": len(actor_events),
            "last_active": last_active,
            "top_actions": top_actions,
        }

    # ---------------------------------------------------------------- render

    def render_text(self) -> str:
        """Render a plain-text dashboard."""
        m = self.metrics()
        lines = [
            "=== Audit Dashboard ===",
            f"Total events: {m.total_events}",
            f"Active actors: {m.active_actors}",
            f"Risk score: {m.risk_score}/100",
            f"Anomalies: {m.anomaly_count}",
            "",
            "Top actors:",
        ]
        for actor, count in m.top_actors:
            lines.append(f"  {actor}: {count}")
        lines.append("")
        lines.append("Top actions:")
        for action, count in m.top_actions:
            lines.append(f"  {action}: {count}")
        lines.append("")
        lines.append(f"Recent events: {len(m.recent_events)}")
        for e in m.recent_events[-5:]:
            lines.append(f"  [{e.event_type}] {e.actor} {e.action} {e.resource}")
        return "\n".join(lines)

    # ---------------------------------------------------------------- summary

    def summary(self) -> dict[str, Any]:
        """Return summary dict."""
        m = self.metrics()
        return {
            "total_events": m.total_events,
            "active_actors": m.active_actors,
            "risk_score": m.risk_score,
            "anomaly_count": m.anomaly_count,
        }
