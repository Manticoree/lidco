"""LinearClient — simulated GraphQL API for Linear integration.

Provides issue CRUD and team listing against an in-memory store.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Issue:
    """A Linear issue."""

    id: str
    title: str
    team: str
    status: str = "Todo"
    description: str = ""
    priority: int = 0
    labels: list[str] = field(default_factory=list)
    assignee: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class Team:
    """A Linear team."""

    id: str
    name: str
    key: str


class LinearClient:
    """Simulated Linear GraphQL client backed by an in-memory store."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._issues: dict[str, Issue] = {}
        self._teams: list[Team] = [
            Team(id="team-eng", name="Engineering", key="ENG"),
            Team(id="team-des", name="Design", key="DES"),
            Team(id="team-ops", name="Operations", key="OPS"),
        ]

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    def get_issue(self, issue_id: str) -> Issue:
        """Fetch an issue by ID.

        Raises:
            KeyError: If the issue does not exist.
        """
        if issue_id not in self._issues:
            raise KeyError(f"Issue not found: {issue_id}")
        return self._issues[issue_id]

    def list_issues(self, team: str, status: str | None = None) -> list[Issue]:
        """List issues for a team, optionally filtered by status."""
        results: list[Issue] = []
        for issue in self._issues.values():
            if issue.team != team:
                continue
            if status is not None and issue.status != status:
                continue
            results.append(issue)
        return sorted(results, key=lambda i: i.created_at, reverse=True)

    def create_issue(
        self,
        title: str,
        team: str,
        *,
        description: str = "",
        priority: int = 0,
        labels: list[str] | None = None,
        assignee: str | None = None,
    ) -> Issue:
        """Create a new issue and return it."""
        if not title:
            raise ValueError("Title must not be empty")
        if not team:
            raise ValueError("Team must not be empty")
        issue_id = f"LIN-{uuid.uuid4().hex[:8].upper()}"
        now = time.time()
        issue = Issue(
            id=issue_id,
            title=title,
            team=team,
            description=description,
            priority=priority,
            labels=labels or [],
            assignee=assignee,
            created_at=now,
            updated_at=now,
        )
        self._issues[issue_id] = issue
        return issue

    def update_issue(self, issue_id: str, **kwargs) -> Issue:
        """Update fields on an existing issue.

        Raises:
            KeyError: If the issue does not exist.
        """
        issue = self.get_issue(issue_id)
        allowed = {"title", "status", "description", "priority", "labels", "assignee"}
        for key, value in kwargs.items():
            if key not in allowed:
                raise ValueError(f"Cannot update field: {key}")
            setattr(issue, key, value)
        issue.updated_at = time.time()
        return issue

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def list_teams(self) -> list[Team]:
        """Return all teams."""
        return list(self._teams)
