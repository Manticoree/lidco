"""SprintPlanner — sprint management and capacity planning."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from lidco.jira.client import JiraClient, Issue


@dataclass
class Sprint:
    """Represents a Jira sprint."""

    id: str
    name: str
    goal: str = ""
    status: str = "future"  # "future" | "active" | "closed"
    issue_keys: list[str] = field(default_factory=list)
    estimates: dict[str, int] = field(default_factory=dict)
    capacity_points: int = 0
    started_at: float = 0.0
    ended_at: float = 0.0
    created_at: float = field(default_factory=time.time)


class SprintPlanner:
    """Sprint creation, issue assignment, estimation, and capacity planning."""

    def __init__(self, client: JiraClient) -> None:
        self._client = client
        self._sprints: dict[str, Sprint] = {}
        self._counter: int = 0

    @property
    def client(self) -> JiraClient:
        return self._client

    def create_sprint(self, name: str, goal: str = "", capacity_points: int = 0) -> Sprint:
        """Create a new sprint."""
        self._counter += 1
        sprint_id = f"sprint-{self._counter}"
        sprint = Sprint(
            id=sprint_id,
            name=name,
            goal=goal,
            capacity_points=capacity_points,
        )
        self._sprints[sprint_id] = sprint
        return sprint

    def get_sprint(self, sprint_id: str) -> Sprint:
        """Get a sprint by ID. Raises KeyError if not found."""
        if sprint_id not in self._sprints:
            raise KeyError(f"Sprint {sprint_id} not found")
        return self._sprints[sprint_id]

    def start_sprint(self, sprint_id: str) -> Sprint:
        """Activate a sprint."""
        sprint = self.get_sprint(sprint_id)
        updated = Sprint(
            id=sprint.id,
            name=sprint.name,
            goal=sprint.goal,
            status="active",
            issue_keys=list(sprint.issue_keys),
            estimates=dict(sprint.estimates),
            capacity_points=sprint.capacity_points,
            started_at=time.time(),
            ended_at=sprint.ended_at,
            created_at=sprint.created_at,
        )
        self._sprints[sprint_id] = updated
        return updated

    def close_sprint(self, sprint_id: str) -> Sprint:
        """Close a sprint."""
        sprint = self.get_sprint(sprint_id)
        updated = Sprint(
            id=sprint.id,
            name=sprint.name,
            goal=sprint.goal,
            status="closed",
            issue_keys=list(sprint.issue_keys),
            estimates=dict(sprint.estimates),
            capacity_points=sprint.capacity_points,
            started_at=sprint.started_at,
            ended_at=time.time(),
            created_at=sprint.created_at,
        )
        self._sprints[sprint_id] = updated
        return updated

    def add_issue(self, sprint_id: str, issue_key: str) -> Sprint:
        """Add an issue to a sprint. Verifies issue exists."""
        self._client.get_issue(issue_key)
        sprint = self.get_sprint(sprint_id)
        if issue_key in sprint.issue_keys:
            return sprint
        new_keys = list(sprint.issue_keys) + [issue_key]
        updated = Sprint(
            id=sprint.id,
            name=sprint.name,
            goal=sprint.goal,
            status=sprint.status,
            issue_keys=new_keys,
            estimates=dict(sprint.estimates),
            capacity_points=sprint.capacity_points,
            started_at=sprint.started_at,
            ended_at=sprint.ended_at,
            created_at=sprint.created_at,
        )
        self._sprints[sprint_id] = updated
        return updated

    def remove_issue(self, sprint_id: str, issue_key: str) -> Sprint:
        """Remove an issue from a sprint."""
        sprint = self.get_sprint(sprint_id)
        new_keys = [k for k in sprint.issue_keys if k != issue_key]
        new_estimates = {k: v for k, v in sprint.estimates.items() if k != issue_key}
        updated = Sprint(
            id=sprint.id,
            name=sprint.name,
            goal=sprint.goal,
            status=sprint.status,
            issue_keys=new_keys,
            estimates=new_estimates,
            capacity_points=sprint.capacity_points,
            started_at=sprint.started_at,
            ended_at=sprint.ended_at,
            created_at=sprint.created_at,
        )
        self._sprints[sprint_id] = updated
        return updated

    def estimate(self, issue_key: str, points: int, sprint_id: str | None = None) -> dict:
        """Set story point estimate for an issue in a sprint.

        If sprint_id is None, searches all sprints for the issue.
        """
        target_sprints = (
            [self.get_sprint(sprint_id)] if sprint_id
            else [s for s in self._sprints.values() if issue_key in s.issue_keys]
        )
        if not target_sprints:
            raise KeyError(f"Issue {issue_key} not found in any sprint")
        sprint = target_sprints[0]
        new_estimates = dict(sprint.estimates)
        new_estimates[issue_key] = points
        updated = Sprint(
            id=sprint.id,
            name=sprint.name,
            goal=sprint.goal,
            status=sprint.status,
            issue_keys=list(sprint.issue_keys),
            estimates=new_estimates,
            capacity_points=sprint.capacity_points,
            started_at=sprint.started_at,
            ended_at=sprint.ended_at,
            created_at=sprint.created_at,
        )
        self._sprints[sprint.id] = updated
        return {"issue_key": issue_key, "points": points, "sprint_id": sprint.id}

    def capacity(self, sprint_id: str) -> dict:
        """Calculate capacity usage for a sprint."""
        sprint = self.get_sprint(sprint_id)
        total_estimated = sum(sprint.estimates.values())
        remaining = sprint.capacity_points - total_estimated
        return {
            "sprint_id": sprint_id,
            "sprint_name": sprint.name,
            "capacity_points": sprint.capacity_points,
            "total_estimated": total_estimated,
            "remaining": remaining,
            "issue_count": len(sprint.issue_keys),
            "estimated_count": len(sprint.estimates),
            "unestimated_count": len(sprint.issue_keys) - len(sprint.estimates),
        }

    def list_sprints(self, status: str | None = None) -> list[Sprint]:
        """List all sprints, optionally filtered by status."""
        sprints = list(self._sprints.values())
        if status is not None:
            sprints = [s for s in sprints if s.status == status]
        return sprints

    def sprint_issues(self, sprint_id: str) -> list[Issue]:
        """Get all issues in a sprint."""
        sprint = self.get_sprint(sprint_id)
        issues: list[Issue] = []
        for key in sprint.issue_keys:
            try:
                issues.append(self._client.get_issue(key))
            except KeyError:
                pass
        return issues
