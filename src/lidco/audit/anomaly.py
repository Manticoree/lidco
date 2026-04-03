"""AnomalyDetector — Detect unusual audit patterns and generate alerts."""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from lidco.audit.event_store import AuditEventStore


@dataclass(frozen=True)
class Anomaly:
    """Detected anomaly in audit data."""

    type: str
    severity: str  # "low" | "medium" | "high" | "critical"
    description: str
    actor: str
    timestamp: float
    evidence: list[str]


_SEVERITY_WEIGHT = {"low": 1, "medium": 2, "high": 4, "critical": 8}


class AnomalyDetector:
    """Detect unusual patterns in audit events.

    Parameters
    ----------
    store:
        The :class:`AuditEventStore` to analyze.
    thresholds:
        Optional overrides for detection thresholds.
        Keys: ``bulk_count`` (default 50), ``bulk_window_seconds`` (default 300),
        ``escalation_actions`` (list of action keywords indicating privilege changes).
    """

    DEFAULT_THRESHOLDS: dict[str, Any] = {
        "bulk_count": 50,
        "bulk_window_seconds": 300,
        "escalation_actions": ["role_change", "grant_admin", "elevate", "sudo", "permission_change"],
    }

    def __init__(self, store: AuditEventStore, thresholds: dict[str, Any] | None = None) -> None:
        self._store = store
        self._thresholds: dict[str, Any] = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._anomalies: list[Anomaly] = []

    # -------------------------------------------------------- privilege escalation

    def detect_privilege_escalation(self) -> list[Anomaly]:
        """Look for rapid role changes or admin-access patterns."""
        escalation_actions = self._thresholds["escalation_actions"]
        events = self._store.events()
        anomalies: list[Anomaly] = []

        # Group escalation events by actor
        actor_escalations: dict[str, list[float]] = defaultdict(list)
        for e in events:
            if any(kw in e.action.lower() for kw in escalation_actions):
                actor_escalations[e.actor].append(e.timestamp)

        window = self._thresholds["bulk_window_seconds"]
        for actor, timestamps in actor_escalations.items():
            timestamps.sort()
            # Flag if multiple escalation events in a short window
            if len(timestamps) >= 2:
                for i in range(len(timestamps) - 1):
                    if timestamps[i + 1] - timestamps[i] < window:
                        anomalies.append(Anomaly(
                            type="privilege_escalation",
                            severity="critical",
                            description=f"Rapid privilege changes by {actor}",
                            actor=actor,
                            timestamp=timestamps[i + 1],
                            evidence=[
                                f"{len(timestamps)} escalation events",
                                f"Window: {window}s",
                            ],
                        ))
                        break
            elif len(timestamps) == 1:
                anomalies.append(Anomaly(
                    type="privilege_escalation",
                    severity="high",
                    description=f"Privilege escalation action by {actor}",
                    actor=actor,
                    timestamp=timestamps[0],
                    evidence=["Single escalation event detected"],
                ))

        return anomalies

    # -------------------------------------------------------- off-hours

    def detect_off_hours(self, business_hours: tuple[int, int] = (9, 17)) -> list[Anomaly]:
        """Detect events outside business hours."""
        events = self._store.events()
        anomalies: list[Anomaly] = []
        start_h, end_h = business_hours

        actor_off: dict[str, int] = defaultdict(int)
        for e in events:
            dt = datetime.fromtimestamp(e.timestamp)
            hour = dt.hour
            if hour < start_h or hour >= end_h:
                actor_off[e.actor] += 1

        for actor, count in actor_off.items():
            severity = "low" if count < 5 else ("medium" if count < 20 else "high")
            anomalies.append(Anomaly(
                type="off_hours",
                severity=severity,
                description=f"{actor} had {count} event(s) outside business hours ({start_h}:00-{end_h}:00)",
                actor=actor,
                timestamp=time.time(),
                evidence=[f"{count} off-hours events"],
            ))

        return anomalies

    # -------------------------------------------------------- bulk operations

    def detect_bulk_operations(self, threshold: int = 50) -> list[Anomaly]:
        """Detect actors performing many operations in a short window."""
        events = self._store.events()
        anomalies: list[Anomaly] = []
        window = self._thresholds["bulk_window_seconds"]

        # Group by actor
        actor_events: dict[str, list[float]] = defaultdict(list)
        for e in events:
            actor_events[e.actor].append(e.timestamp)

        for actor, timestamps in actor_events.items():
            timestamps.sort()
            if len(timestamps) < threshold:
                continue
            # Sliding window
            start = 0
            for end in range(len(timestamps)):
                while timestamps[end] - timestamps[start] > window:
                    start += 1
                count = end - start + 1
                if count >= threshold:
                    anomalies.append(Anomaly(
                        type="bulk_operations",
                        severity="high",
                        description=f"{actor} performed {count} operations in {window}s",
                        actor=actor,
                        timestamp=timestamps[end],
                        evidence=[f"{count} ops in {window}s window"],
                    ))
                    break

        return anomalies

    # -------------------------------------------------------- detect all

    def detect_all(self) -> list[Anomaly]:
        """Run all detectors and cache results."""
        results: list[Anomaly] = []
        results.extend(self.detect_privilege_escalation())
        results.extend(self.detect_off_hours())
        results.extend(self.detect_bulk_operations())
        self._anomalies = results
        return results

    def anomalies(self) -> list[Anomaly]:
        """Return cached results from the last :meth:`detect_all` call."""
        return list(self._anomalies)

    # -------------------------------------------------------- summary

    def summary(self) -> dict[str, Any]:
        """Return summary of detected anomalies."""
        by_type: dict[str, int] = defaultdict(int)
        by_severity: dict[str, int] = defaultdict(int)
        for a in self._anomalies:
            by_type[a.type] += 1
            by_severity[a.severity] += 1
        return {
            "total_anomalies": len(self._anomalies),
            "by_type": dict(by_type),
            "by_severity": dict(by_severity),
        }
