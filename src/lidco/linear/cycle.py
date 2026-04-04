"""CyclePlanner — manage Linear cycles (sprints).

Provides cycle creation, issue assignment, scope and estimate tracking.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from lidco.linear.client import LinearClient


@dataclass
class Cycle:
    """A Linear cycle (sprint)."""

    id: str
    name: str
    start: float
    end: float
    issue_ids: list[str] = field(default_factory=list)


class CyclePlanner:
    """Manage Linear cycles and their issue assignments."""

    def __init__(self, client: LinearClient | None = None) -> None:
        self._client = client or LinearClient()
        self._cycles: dict[str, Cycle] = {}

    @property
    def client(self) -> LinearClient:
        return self._client

    def create_cycle(self, name: str, start: float, end: float) -> Cycle:
        """Create a new cycle.

        Raises:
            ValueError: If name is empty or end <= start.
        """
        if not name:
            raise ValueError("Cycle name must not be empty")
        if end <= start:
            raise ValueError("Cycle end must be after start")
        cycle_id = f"CYC-{uuid.uuid4().hex[:8].upper()}"
        cycle = Cycle(id=cycle_id, name=name, start=start, end=end)
        self._cycles[cycle_id] = cycle
        return cycle

    def get_cycle(self, cycle_id: str) -> Cycle:
        """Fetch a cycle by ID.

        Raises:
            KeyError: If the cycle does not exist.
        """
        if cycle_id not in self._cycles:
            raise KeyError(f"Cycle not found: {cycle_id}")
        return self._cycles[cycle_id]

    def add_issue(self, cycle_id: str, issue_id: str) -> None:
        """Add an issue to a cycle.

        Raises:
            KeyError: If the cycle or issue does not exist.
        """
        cycle = self.get_cycle(cycle_id)
        # Verify issue exists
        self._client.get_issue(issue_id)
        if issue_id not in cycle.issue_ids:
            cycle.issue_ids.append(issue_id)

    def scope(self, cycle_id: str) -> dict:
        """Return the scope summary for a cycle.

        Returns:
            dict with total, by_status, and issue_ids.
        """
        cycle = self.get_cycle(cycle_id)
        by_status: dict[str, int] = {}
        for iid in cycle.issue_ids:
            try:
                issue = self._client.get_issue(iid)
                by_status[issue.status] = by_status.get(issue.status, 0) + 1
            except KeyError:
                by_status["Unknown"] = by_status.get("Unknown", 0) + 1
        return {
            "cycle_id": cycle_id,
            "cycle_name": cycle.name,
            "total": len(cycle.issue_ids),
            "by_status": by_status,
            "issue_ids": list(cycle.issue_ids),
        }

    def estimates(self, cycle_id: str) -> dict:
        """Return estimate/priority summary for a cycle.

        Returns:
            dict with total_points (sum of priorities), avg_priority,
            and per-issue breakdowns.
        """
        cycle = self.get_cycle(cycle_id)
        items: list[dict] = []
        total_points = 0
        for iid in cycle.issue_ids:
            try:
                issue = self._client.get_issue(iid)
                items.append({
                    "issue_id": iid,
                    "title": issue.title,
                    "priority": issue.priority,
                    "status": issue.status,
                })
                total_points += issue.priority
            except KeyError:
                items.append({
                    "issue_id": iid,
                    "title": "Unknown",
                    "priority": 0,
                    "status": "Unknown",
                })
        count = len(items)
        return {
            "cycle_id": cycle_id,
            "total_points": total_points,
            "avg_priority": total_points / count if count else 0.0,
            "items": items,
        }
