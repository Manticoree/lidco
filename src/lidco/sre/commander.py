"""Incident Commander — incident management, severity, comms templates, status page, postmortem.

Stdlib only.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IncidentError(Exception):
    """Raised when an incident operation fails."""


class Severity(str, Enum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


class IncidentStatus(str, Enum):
    DECLARED = "declared"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"


_STATUS_ORDER = [
    IncidentStatus.DECLARED,
    IncidentStatus.INVESTIGATING,
    IncidentStatus.IDENTIFIED,
    IncidentStatus.MITIGATING,
    IncidentStatus.RESOLVED,
    IncidentStatus.POSTMORTEM,
]


@dataclass
class StatusUpdate:
    """A timestamped update on an incident."""

    message: str
    status: IncidentStatus
    author: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class CommunicationTemplate:
    """Template for incident communications."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    severity: Severity = Severity.SEV3
    template: str = ""

    def render(self, **kwargs: str) -> str:
        result = self.template
        for key, val in kwargs.items():
            result = result.replace(f"{{{{{key}}}}}", val)
        return result


@dataclass
class Incident:
    """A tracked incident."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    severity: Severity = Severity.SEV3
    status: IncidentStatus = IncidentStatus.DECLARED
    commander: str = ""
    description: str = ""
    created_at: float = field(default_factory=time.time)
    resolved_at: float | None = None
    updates: list[StatusUpdate] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def duration_seconds(self) -> float:
        end = self.resolved_at if self.resolved_at else time.time()
        return end - self.created_at

    def is_active(self) -> bool:
        return self.status not in (IncidentStatus.RESOLVED, IncidentStatus.POSTMORTEM)


@dataclass
class StatusPageEntry:
    """Public status page entry for an incident."""

    incident_id: str
    title: str
    severity: Severity
    status: IncidentStatus
    message: str
    updated_at: float = field(default_factory=time.time)


@dataclass
class PostmortemReport:
    """Postmortem document for a resolved incident."""

    incident_id: str
    title: str
    severity: Severity
    duration_seconds: float
    timeline: list[StatusUpdate]
    root_cause: str = ""
    impact: str = ""
    action_items: list[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def summary(self) -> str:
        mins = self.duration_seconds / 60
        lines = [
            f"Postmortem: {self.title}",
            f"Severity: {self.severity.value}  Duration: {mins:.1f}m",
            f"Root cause: {self.root_cause or 'TBD'}",
            f"Impact: {self.impact or 'TBD'}",
            f"Action items: {len(self.action_items)}",
        ]
        return "\n".join(lines)


class IncidentCommander:
    """Manage incidents through their lifecycle."""

    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        self._templates: dict[str, CommunicationTemplate] = {}
        self._status_page: list[StatusPageEntry] = []

    # ---- Incident CRUD ----

    def declare(self, title: str, severity: Severity, commander: str = "", description: str = "") -> Incident:
        """Declare a new incident."""
        if not title:
            raise IncidentError("Incident title is required")
        inc = Incident(title=title, severity=severity, commander=commander, description=description)
        inc.updates.append(StatusUpdate(message=f"Incident declared: {title}", status=IncidentStatus.DECLARED, author=commander))
        self._incidents[inc.id] = inc
        return inc

    def get(self, incident_id: str) -> Incident:
        if incident_id not in self._incidents:
            raise IncidentError(f"Incident not found: {incident_id}")
        return self._incidents[incident_id]

    def list_incidents(self, active_only: bool = False) -> list[Incident]:
        incidents = list(self._incidents.values())
        if active_only:
            incidents = [i for i in incidents if i.is_active()]
        return incidents

    # ---- Status transitions ----

    def update_status(self, incident_id: str, status: IncidentStatus, message: str, author: str = "") -> Incident:
        inc = self.get(incident_id)
        inc.status = status
        if status == IncidentStatus.RESOLVED and inc.resolved_at is None:
            inc.resolved_at = time.time()
        inc.updates.append(StatusUpdate(message=message, status=status, author=author))
        return inc

    # ---- Communication templates ----

    def add_template(self, template: CommunicationTemplate) -> CommunicationTemplate:
        if not template.name:
            raise IncidentError("Template name is required")
        self._templates[template.id] = template
        return template

    def get_template(self, template_id: str) -> CommunicationTemplate:
        if template_id not in self._templates:
            raise IncidentError(f"Template not found: {template_id}")
        return self._templates[template_id]

    def list_templates(self) -> list[CommunicationTemplate]:
        return list(self._templates.values())

    def render_template(self, template_id: str, **kwargs: str) -> str:
        tpl = self.get_template(template_id)
        return tpl.render(**kwargs)

    # ---- Status page ----

    def publish_status(self, incident_id: str, message: str) -> StatusPageEntry:
        inc = self.get(incident_id)
        entry = StatusPageEntry(
            incident_id=inc.id,
            title=inc.title,
            severity=inc.severity,
            status=inc.status,
            message=message,
        )
        self._status_page.append(entry)
        return entry

    def status_page(self) -> list[StatusPageEntry]:
        return list(self._status_page)

    # ---- Postmortem ----

    def generate_postmortem(self, incident_id: str, root_cause: str = "", impact: str = "", action_items: list[str] | None = None) -> PostmortemReport:
        inc = self.get(incident_id)
        if inc.is_active():
            raise IncidentError("Cannot generate postmortem for an active incident")
        return PostmortemReport(
            incident_id=inc.id,
            title=inc.title,
            severity=inc.severity,
            duration_seconds=inc.duration_seconds(),
            timeline=list(inc.updates),
            root_cause=root_cause,
            impact=impact,
            action_items=action_items or [],
        )
