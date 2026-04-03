"""Forensics collection — evidence, timeline, chain of custody."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Evidence:
    """A piece of forensic evidence."""

    id: str
    incident_id: str
    type: str  # log / file_change / api_call / session
    content: str
    collected_at: float
    collector: str = "system"


class ForensicsCollector:
    """Collect and manage forensic evidence."""

    def __init__(self) -> None:
        self._evidence: list[Evidence] = []
        self._custody: dict[str, list[dict]] = {}  # evidence_id -> custody entries

    def collect(
        self,
        incident_id: str,
        evidence_type: str,
        content: str,
        collector: str = "system",
    ) -> Evidence:
        """Collect a new piece of evidence."""
        ev = Evidence(
            id=uuid.uuid4().hex[:12],
            incident_id=incident_id,
            type=evidence_type,
            content=content,
            collected_at=time.time(),
            collector=collector,
        )
        self._evidence.append(ev)
        self._custody[ev.id] = [
            {"action": "collected", "by": collector, "timestamp": ev.collected_at}
        ]
        return ev

    def get_evidence(self, incident_id: str) -> list[Evidence]:
        """Return all evidence for *incident_id*."""
        return [e for e in self._evidence if e.incident_id == incident_id]

    def timeline(self, incident_id: str) -> list[Evidence]:
        """Evidence for *incident_id* sorted by collection time."""
        return sorted(self.get_evidence(incident_id), key=lambda e: e.collected_at)

    def export(self, incident_id: str, format: str = "json") -> str:
        """Export evidence for *incident_id*."""
        items = self.get_evidence(incident_id)
        data = [
            {
                "id": e.id,
                "incident_id": e.incident_id,
                "type": e.type,
                "content": e.content,
                "collected_at": e.collected_at,
                "collector": e.collector,
            }
            for e in items
        ]
        if format == "json":
            return json.dumps(data, indent=2)
        # Fallback: simple text
        lines: list[str] = []
        for d in data:
            lines.append(f"[{d['type']}] {d['content']} (by {d['collector']})")
        return "\n".join(lines)

    def chain_of_custody(self, evidence_id: str) -> list[dict]:
        """Return custody chain for *evidence_id*."""
        return list(self._custody.get(evidence_id, []))

    def all_evidence(self) -> list[Evidence]:
        """Return all collected evidence."""
        return list(self._evidence)

    def summary(self) -> dict:
        """Summary stats."""
        by_type: dict[str, int] = {}
        incidents: set[str] = set()
        for e in self._evidence:
            by_type[e.type] = by_type.get(e.type, 0) + 1
            incidents.add(e.incident_id)
        return {
            "total_evidence": len(self._evidence),
            "incidents_covered": len(incidents),
            "by_type": by_type,
        }
