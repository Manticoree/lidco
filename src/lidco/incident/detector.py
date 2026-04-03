"""Incident detection — unusual patterns, alert escalation."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Incident:
    """An identified security incident."""

    id: str
    type: str  # data_exfiltration / privilege_escalation / brute_force / anomalous_access / policy_violation
    severity: str  # low / medium / high / critical
    description: str
    actor: str
    timestamp: float
    indicators: list[str] = field(default_factory=list)


_VALID_TYPES = frozenset(
    {"data_exfiltration", "privilege_escalation", "brute_force", "anomalous_access", "policy_violation"}
)
_VALID_SEVERITIES = frozenset({"low", "medium", "high", "critical"})


class IncidentDetector:
    """Detect security incidents from event streams."""

    def __init__(self, thresholds: dict | None = None) -> None:
        self._thresholds: dict = thresholds or {}
        self._incidents: list[Incident] = []

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def _make_incident(
        self,
        itype: str,
        severity: str,
        description: str,
        actor: str,
        indicators: list[str] | None = None,
    ) -> Incident:
        inc = Incident(
            id=uuid.uuid4().hex[:12],
            type=itype,
            severity=severity,
            description=description,
            actor=actor,
            timestamp=time.time(),
            indicators=indicators or [],
        )
        self._incidents.append(inc)
        return inc

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def analyze_events(self, events: list[dict]) -> list[Incident]:
        """Run all detectors on *events* and return new incidents."""
        found: list[Incident] = []
        found.extend(self.detect_exfiltration(events))
        found.extend(self.detect_brute_force(events))
        found.extend(self.detect_policy_violation(events))
        # anomalous_access: events with type=="access" from unknown actors
        known_actors: set[str] = set()
        for ev in events:
            actor = ev.get("actor", "")
            if ev.get("type") == "auth_success":
                known_actors.add(actor)
        for ev in events:
            if ev.get("type") == "access" and ev.get("actor", "") not in known_actors:
                inc = self._make_incident(
                    "anomalous_access",
                    "medium",
                    f"Anomalous access by {ev.get('actor', 'unknown')}",
                    ev.get("actor", "unknown"),
                    [f"resource={ev.get('resource', '?')}"],
                )
                found.append(inc)
        return found

    def detect_exfiltration(self, events: list[dict], threshold: int | None = None) -> list[Incident]:
        """Detect large data transfers exceeding *threshold* bytes."""
        thr = threshold if threshold is not None else self._thresholds.get("exfiltration", 100)
        actor_bytes: dict[str, int] = {}
        for ev in events:
            if ev.get("type") == "data_transfer":
                actor = ev.get("actor", "unknown")
                actor_bytes[actor] = actor_bytes.get(actor, 0) + ev.get("bytes", 0)
        found: list[Incident] = []
        for actor, total in actor_bytes.items():
            if total >= thr:
                inc = self._make_incident(
                    "data_exfiltration",
                    "critical",
                    f"Data exfiltration by {actor}: {total} bytes",
                    actor,
                    [f"bytes={total}"],
                )
                found.append(inc)
        return found

    def detect_brute_force(self, events: list[dict], threshold: int | None = None) -> list[Incident]:
        """Detect repeated auth failures exceeding *threshold*."""
        thr = threshold if threshold is not None else self._thresholds.get("brute_force", 10)
        actor_fails: dict[str, int] = {}
        for ev in events:
            if ev.get("type") == "auth_failure":
                actor = ev.get("actor", "unknown")
                actor_fails[actor] = actor_fails.get(actor, 0) + 1
        found: list[Incident] = []
        for actor, count in actor_fails.items():
            if count >= thr:
                inc = self._make_incident(
                    "brute_force",
                    "high",
                    f"Brute force by {actor}: {count} failures",
                    actor,
                    [f"failures={count}"],
                )
                found.append(inc)
        return found

    def detect_policy_violation(
        self, events: list[dict], policies: list[str] | None = None
    ) -> list[Incident]:
        """Detect events that violate *policies*."""
        pol_set = set(policies) if policies else {"no_root_access", "no_sensitive_download"}
        found: list[Incident] = []
        for ev in events:
            violated = ev.get("policy")
            if violated and violated in pol_set:
                inc = self._make_incident(
                    "policy_violation",
                    "high",
                    f"Policy '{violated}' violated by {ev.get('actor', 'unknown')}",
                    ev.get("actor", "unknown"),
                    [f"policy={violated}"],
                )
                found.append(inc)
        return found

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def incidents(self) -> list[Incident]:
        """Return all detected incidents."""
        return list(self._incidents)

    def by_severity(self, severity: str) -> list[Incident]:
        """Return incidents matching *severity*."""
        return [i for i in self._incidents if i.severity == severity]

    def summary(self) -> dict:
        """Return summary stats."""
        by_type: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        for i in self._incidents:
            by_type[i.type] = by_type.get(i.type, 0) + 1
            by_sev[i.severity] = by_sev.get(i.severity, 0) + 1
        return {
            "total": len(self._incidents),
            "by_type": by_type,
            "by_severity": by_sev,
        }
