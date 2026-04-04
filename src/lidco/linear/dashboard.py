"""LinearDashboard — team velocity, distribution, cycle progress, SLA tracking.

Provides analytics views over Linear data for team health monitoring.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from lidco.linear.client import LinearClient
from lidco.linear.cycle import CyclePlanner


class LinearDashboard:
    """Dashboard analytics for Linear integration."""

    def __init__(
        self,
        client: LinearClient | None = None,
        planner: CyclePlanner | None = None,
    ) -> None:
        self._client = client or LinearClient()
        self._planner = planner or CyclePlanner(self._client)

    @property
    def client(self) -> LinearClient:
        return self._client

    @property
    def planner(self) -> CyclePlanner:
        return self._planner

    def velocity(self, team: str, cycles: int = 3) -> list[dict]:
        """Calculate velocity across recent cycles.

        Returns a list of dicts with cycle_id, name, completed, total.
        The *cycles* parameter limits how many most-recent cycles to include.
        """
        all_cycles = sorted(
            self._planner._cycles.values(), key=lambda c: c.start, reverse=True
        )
        results: list[dict] = []
        for cyc in all_cycles[:cycles]:
            scope = self._planner.scope(cyc.id)
            completed = scope["by_status"].get("Done", 0)
            results.append({
                "cycle_id": cyc.id,
                "name": cyc.name,
                "completed": completed,
                "total": scope["total"],
            })
        return results

    def distribution(self, team: str) -> dict:
        """Return issue distribution by status for a team.

        Returns:
            dict mapping status -> count.
        """
        issues = self._client.list_issues(team)
        dist: dict[str, int] = {}
        for issue in issues:
            dist[issue.status] = dist.get(issue.status, 0) + 1
        return dist

    def cycle_progress(self, cycle_id: str) -> dict:
        """Return progress for a specific cycle.

        Returns:
            dict with cycle_id, name, total, completed, percent, time_remaining.
        """
        scope = self._planner.scope(cycle_id)
        cycle = self._planner.get_cycle(cycle_id)
        completed = scope["by_status"].get("Done", 0)
        total = scope["total"]
        percent = (completed / total * 100.0) if total else 0.0
        remaining = max(0.0, cycle.end - time.time())
        return {
            "cycle_id": cycle_id,
            "name": cycle.name,
            "total": total,
            "completed": completed,
            "percent": round(percent, 1),
            "time_remaining_s": round(remaining, 1),
        }

    def sla_tracking(self, team: str) -> list[dict]:
        """Return SLA status for open issues on a team.

        Issues with priority >= 3 are considered high-priority and have
        a 24-hour SLA from creation. Lower-priority issues have 72 hours.

        Returns:
            list of dicts with issue_id, title, priority, sla_hours,
            elapsed_hours, within_sla.
        """
        issues = self._client.list_issues(team)
        now = time.time()
        results: list[dict] = []
        for issue in issues:
            if issue.status in ("Done", "Cancelled"):
                continue
            sla_hours = 24.0 if issue.priority >= 3 else 72.0
            elapsed = (now - issue.created_at) / 3600.0
            results.append({
                "issue_id": issue.id,
                "title": issue.title,
                "priority": issue.priority,
                "sla_hours": sla_hours,
                "elapsed_hours": round(elapsed, 2),
                "within_sla": elapsed <= sla_hours,
            })
        return results
