"""JiraReporter — sprint reports, velocity, burndown, predictions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lidco.jira.client import JiraClient
from lidco.jira.sprint import SprintPlanner, Sprint


@dataclass
class VelocityEntry:
    """Velocity data for a single sprint."""

    sprint_id: str
    sprint_name: str
    committed: int = 0
    completed: int = 0


class JiraReporter:
    """Generate sprint reports: velocity, burndown, predictions."""

    def __init__(self, planner: SprintPlanner) -> None:
        self._planner = planner

    @property
    def planner(self) -> SprintPlanner:
        return self._planner

    def velocity(self, sprints: list[str] | None = None) -> list[VelocityEntry]:
        """Calculate velocity for given sprint IDs (or all closed sprints).

        Committed = sum of estimates. Completed = estimates of Done issues.
        """
        if sprints is None:
            targets = self._planner.list_sprints(status="closed")
        else:
            targets = [self._planner.get_sprint(sid) for sid in sprints]

        entries: list[VelocityEntry] = []
        for sprint in targets:
            committed = sum(sprint.estimates.values())
            completed = 0
            for key, pts in sprint.estimates.items():
                try:
                    issue = self._planner.client.get_issue(key)
                    if issue.status == "Done":
                        completed += pts
                except KeyError:
                    pass
            entries.append(VelocityEntry(
                sprint_id=sprint.id,
                sprint_name=sprint.name,
                committed=committed,
                completed=completed,
            ))
        return entries

    def burndown(self, sprint_id: str) -> list[dict[str, Any]]:
        """Generate burndown data for a sprint.

        Returns list of dicts with day, remaining_points, completed_points.
        Simulates daily progress from total to zero.
        """
        sprint = self._planner.get_sprint(sprint_id)
        total = sum(sprint.estimates.values())
        if total == 0:
            return [{"day": 0, "remaining_points": 0, "completed_points": 0}]

        # Count done issues
        completed = 0
        for key, pts in sprint.estimates.items():
            try:
                issue = self._planner.client.get_issue(key)
                if issue.status == "Done":
                    completed += pts
            except KeyError:
                pass

        remaining = total - completed
        # Produce a 2-point burndown: start and current
        data = [
            {"day": 0, "remaining_points": total, "completed_points": 0},
            {"day": 1, "remaining_points": remaining, "completed_points": completed},
        ]
        return data

    def completion_prediction(self, sprint_id: str) -> dict[str, Any]:
        """Predict sprint completion based on current progress.

        Returns dict with total, completed, remaining, velocity_per_day,
        estimated_days_remaining.
        """
        sprint = self._planner.get_sprint(sprint_id)
        total = sum(sprint.estimates.values())
        completed = 0
        for key, pts in sprint.estimates.items():
            try:
                issue = self._planner.client.get_issue(key)
                if issue.status == "Done":
                    completed += pts
            except KeyError:
                pass

        remaining = total - completed
        # Use average velocity from closed sprints as baseline
        closed = self._planner.list_sprints(status="closed")
        if closed:
            velocities = []
            for s in closed:
                done_pts = 0
                for k, p in s.estimates.items():
                    try:
                        issue = self._planner.client.get_issue(k)
                        if issue.status == "Done":
                            done_pts += p
                    except KeyError:
                        pass
                velocities.append(done_pts)
            avg_velocity = sum(velocities) / len(velocities) if velocities else 0
        else:
            avg_velocity = completed if completed > 0 else 1

        estimated_days = remaining / avg_velocity if avg_velocity > 0 else float("inf")

        return {
            "sprint_id": sprint_id,
            "total_points": total,
            "completed_points": completed,
            "remaining_points": remaining,
            "avg_velocity": avg_velocity,
            "estimated_days_remaining": estimated_days,
            "on_track": remaining <= avg_velocity,
        }

    def summary(self) -> dict[str, Any]:
        """Overall summary across all sprints."""
        all_sprints = self._planner.list_sprints()
        closed = [s for s in all_sprints if s.status == "closed"]
        active = [s for s in all_sprints if s.status == "active"]
        future = [s for s in all_sprints if s.status == "future"]

        total_committed = 0
        total_completed = 0
        for sprint in all_sprints:
            total_committed += sum(sprint.estimates.values())
            for key, pts in sprint.estimates.items():
                try:
                    issue = self._planner.client.get_issue(key)
                    if issue.status == "Done":
                        total_completed += pts
                except KeyError:
                    pass

        vel = self.velocity()
        avg_vel = (
            sum(v.completed for v in vel) / len(vel) if vel else 0
        )

        return {
            "total_sprints": len(all_sprints),
            "closed_sprints": len(closed),
            "active_sprints": len(active),
            "future_sprints": len(future),
            "total_committed": total_committed,
            "total_completed": total_completed,
            "average_velocity": avg_vel,
        }
