"""Usage aggregation across the fleet."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class UsageEntry:
    """A single usage record."""

    instance_id: str
    team: str
    project: str
    tokens: int
    cost: float
    timestamp: float


class UsageAggregator:
    """Aggregate usage metrics across fleet instances."""

    def __init__(self) -> None:
        self._entries: list[UsageEntry] = []

    def record(
        self,
        instance_id: str,
        team: str,
        project: str,
        tokens: int,
        cost: float,
    ) -> UsageEntry:
        """Record a usage entry."""
        entry = UsageEntry(
            instance_id=instance_id,
            team=team,
            project=project,
            tokens=tokens,
            cost=cost,
            timestamp=time.time(),
        )
        self._entries.append(entry)
        return entry

    def by_team(self) -> dict[str, dict]:
        """Aggregate tokens and cost by team."""
        result: dict[str, dict] = {}
        for e in self._entries:
            if e.team not in result:
                result[e.team] = {"tokens": 0, "cost": 0.0}
            result[e.team]["tokens"] += e.tokens
            result[e.team]["cost"] += e.cost
        return result

    def by_project(self) -> dict[str, dict]:
        """Aggregate tokens and cost by project."""
        result: dict[str, dict] = {}
        for e in self._entries:
            if e.project not in result:
                result[e.project] = {"tokens": 0, "cost": 0.0}
            result[e.project]["tokens"] += e.tokens
            result[e.project]["cost"] += e.cost
        return result

    def by_instance(self) -> dict[str, dict]:
        """Aggregate tokens and cost by instance."""
        result: dict[str, dict] = {}
        for e in self._entries:
            if e.instance_id not in result:
                result[e.instance_id] = {"tokens": 0, "cost": 0.0}
            result[e.instance_id]["tokens"] += e.tokens
            result[e.instance_id]["cost"] += e.cost
        return result

    def total(self) -> dict:
        """Return totals across all entries."""
        tokens = sum(e.tokens for e in self._entries)
        cost = sum(e.cost for e in self._entries)
        return {"tokens": tokens, "cost": cost, "entry_count": len(self._entries)}

    def top_teams(self, limit: int = 10) -> list[tuple[str, float]]:
        """Top teams ranked by cost."""
        teams = self.by_team()
        ranked = sorted(teams.items(), key=lambda x: x[1]["cost"], reverse=True)
        return [(t, d["cost"]) for t, d in ranked[:limit]]

    def export(self, format: str = "json") -> str:
        """Export entries as JSON or CSV."""
        if format == "csv":
            lines = ["instance_id,team,project,tokens,cost,timestamp"]
            for e in self._entries:
                lines.append(
                    f"{e.instance_id},{e.team},{e.project},{e.tokens},{e.cost},{e.timestamp}"
                )
            return "\n".join(lines)
        # default json
        return json.dumps(
            [
                {
                    "instance_id": e.instance_id,
                    "team": e.team,
                    "project": e.project,
                    "tokens": e.tokens,
                    "cost": e.cost,
                    "timestamp": e.timestamp,
                }
                for e in self._entries
            ],
            indent=2,
        )

    def entries(self) -> list[UsageEntry]:
        """Return all entries."""
        return list(self._entries)

    def summary(self) -> dict:
        """Return aggregator summary."""
        totals = self.total()
        return {
            "entry_count": totals["entry_count"],
            "total_tokens": totals["tokens"],
            "total_cost": totals["cost"],
            "teams": len(self.by_team()),
            "projects": len(self.by_project()),
        }
