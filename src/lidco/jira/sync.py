"""IssueSync — bi-directional sync between TODOs and Jira issues."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from lidco.jira.client import JiraClient, Issue


@dataclass
class SyncRecord:
    """Tracks a single sync operation."""

    issue_key: str
    direction: str  # "to_jira" | "from_jira"
    status: str = "pending"  # "pending" | "synced" | "failed"
    timestamp: float = field(default_factory=time.time)
    detail: str = ""


@dataclass
class TodoItem:
    """A lightweight TODO representation for sync."""

    title: str
    done: bool = False
    issue_key: str = ""
    tags: list[str] = field(default_factory=list)


class IssueSync:
    """Bi-directional sync between local TODOs and Jira issues."""

    def __init__(self, client: JiraClient, project: str = "PROJ") -> None:
        self._client = client
        self._project = project
        self._records: list[SyncRecord] = []
        self._pr_links: dict[str, list[str]] = {}

    @property
    def client(self) -> JiraClient:
        return self._client

    def sync_from_todo(self, todos: list[TodoItem]) -> list[Issue]:
        """Create or update Jira issues from TODO items.

        Returns list of created/updated issues.
        """
        results: list[Issue] = []
        for todo in todos:
            if todo.issue_key:
                # Update existing issue
                try:
                    status = "Done" if todo.done else "To Do"
                    issue = self._client.update_issue(
                        todo.issue_key, summary=todo.title, status=status
                    )
                    self._records.append(
                        SyncRecord(
                            issue_key=todo.issue_key,
                            direction="to_jira",
                            status="synced",
                            detail=f"Updated: {todo.title}",
                        )
                    )
                    results.append(issue)
                except KeyError:
                    self._records.append(
                        SyncRecord(
                            issue_key=todo.issue_key,
                            direction="to_jira",
                            status="failed",
                            detail=f"Issue not found: {todo.issue_key}",
                        )
                    )
            else:
                # Create new issue
                issue = self._client.create_issue(
                    summary=todo.title,
                    project=self._project,
                    labels=list(todo.tags),
                )
                self._records.append(
                    SyncRecord(
                        issue_key=issue.key,
                        direction="to_jira",
                        status="synced",
                        detail=f"Created: {todo.title}",
                    )
                )
                results.append(issue)
        return results

    def sync_from_jira(self, jql: str = "") -> list[TodoItem]:
        """Pull Jira issues and convert to TODO items."""
        query = jql or f'project = {self._project}'
        issues = self._client.search_jql(query)
        todos: list[TodoItem] = []
        for issue in issues:
            todo = TodoItem(
                title=issue.summary,
                done=(issue.status == "Done"),
                issue_key=issue.key,
                tags=list(issue.labels),
            )
            todos.append(todo)
            self._records.append(
                SyncRecord(
                    issue_key=issue.key,
                    direction="from_jira",
                    status="synced",
                    detail=f"Pulled: {issue.summary}",
                )
            )
        return todos

    def update_status(self, key: str, status: str) -> Issue:
        """Update the status of a Jira issue."""
        issue = self._client.update_issue(key, status=status)
        self._records.append(
            SyncRecord(
                issue_key=key,
                direction="to_jira",
                status="synced",
                detail=f"Status -> {status}",
            )
        )
        return issue

    def link_pr(self, key: str, pr_url: str) -> None:
        """Link a pull request URL to an issue."""
        # Verify issue exists
        self._client.get_issue(key)
        if key not in self._pr_links:
            self._pr_links[key] = []
        self._pr_links[key].append(pr_url)
        self._records.append(
            SyncRecord(
                issue_key=key,
                direction="to_jira",
                status="synced",
                detail=f"Linked PR: {pr_url}",
            )
        )

    def get_pr_links(self, key: str) -> list[str]:
        """Get all PR links for an issue."""
        return list(self._pr_links.get(key, []))

    def pending_syncs(self) -> list[SyncRecord]:
        """Return all pending sync records."""
        return [r for r in self._records if r.status == "pending"]

    def all_records(self) -> list[SyncRecord]:
        """Return all sync records."""
        return list(self._records)

    def failed_syncs(self) -> list[SyncRecord]:
        """Return all failed sync records."""
        return [r for r in self._records if r.status == "failed"]
