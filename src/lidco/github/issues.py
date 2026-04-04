"""IssueManager — create, update, close, and label GitHub issues (simulated)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Issue:
    """Issue model."""

    id: int
    title: str
    body: str
    state: str = "open"
    labels: list[str] = field(default_factory=list)
    linked_prs: list[int] = field(default_factory=list)


class IssueManager:
    """Simulated issue manager."""

    def __init__(self) -> None:
        self._issues: dict[int, Issue] = {}
        self._next_id: int = 1

    def create(self, title: str, body: str = "") -> Issue:
        """Create a new issue."""
        if not title:
            raise ValueError("title is required")
        issue = Issue(id=self._next_id, title=title, body=body)
        self._issues[issue.id] = issue
        self._next_id += 1
        return issue

    def update(self, issue_id: int, **fields: Any) -> Issue:
        """Update fields on an existing issue."""
        issue = self._issues.get(issue_id)
        if issue is None:
            raise KeyError(f"Issue {issue_id} not found")
        for key, value in fields.items():
            if hasattr(issue, key):
                setattr(issue, key, value)
        return issue

    def close(self, issue_id: int) -> bool:
        """Close an issue. Return True on success."""
        issue = self._issues.get(issue_id)
        if issue is None:
            return False
        issue.state = "closed"
        return True

    def auto_label(self, issue_id: int, labels: list[str]) -> list[str]:
        """Apply labels to an issue and return the full label list."""
        issue = self._issues.get(issue_id)
        if issue is None:
            raise KeyError(f"Issue {issue_id} not found")
        issue.labels = list({*issue.labels, *labels})
        return issue.labels

    def link_to_pr(self, issue_id: int, pr_id: int) -> bool:
        """Link an issue to a PR id."""
        issue = self._issues.get(issue_id)
        if issue is None:
            return False
        if pr_id not in issue.linked_prs:
            issue.linked_prs.append(pr_id)
        return True

    def list_issues(self, filters: dict[str, Any] | None = None) -> list[Issue]:
        """Return issues matching optional *filters*."""
        result = list(self._issues.values())
        if filters:
            if "state" in filters:
                result = [i for i in result if i.state == filters["state"]]
            if "label" in filters:
                result = [i for i in result if filters["label"] in i.labels]
        return result
