"""JiraClient — simulated Jira REST API client.

Provides issue CRUD, JQL search, project listing, and pagination.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Issue:
    """Represents a Jira issue."""

    key: str
    summary: str
    issue_type: str = "Task"
    project: str = "PROJ"
    status: str = "To Do"
    description: str = ""
    assignee: str = ""
    priority: str = "Medium"
    labels: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class Project:
    """Represents a Jira project."""

    key: str
    name: str
    lead: str = ""
    issue_count: int = 0


class JiraClient:
    """Simulated Jira REST API client with in-memory storage."""

    def __init__(self, base_url: str = "https://jira.example.com", token: str = "") -> None:
        self._base_url = base_url
        self._token = token
        self._issues: dict[str, Issue] = {}
        self._projects: dict[str, Project] = {}
        self._counters: dict[str, int] = {}

    @property
    def base_url(self) -> str:
        return self._base_url

    def add_project(self, key: str, name: str, lead: str = "") -> Project:
        """Register a project."""
        proj = Project(key=key, name=name, lead=lead)
        self._projects[key] = proj
        self._counters.setdefault(key, 0)
        return proj

    def list_projects(self) -> list[Project]:
        """Return all registered projects."""
        return list(self._projects.values())

    def create_issue(
        self,
        summary: str,
        issue_type: str = "Task",
        project: str = "PROJ",
        description: str = "",
        assignee: str = "",
        priority: str = "Medium",
        labels: list[str] | None = None,
    ) -> Issue:
        """Create a new issue and return it."""
        if project not in self._projects:
            self.add_project(project, project)
        self._counters[project] = self._counters.get(project, 0) + 1
        key = f"{project}-{self._counters[project]}"
        issue = Issue(
            key=key,
            summary=summary,
            issue_type=issue_type,
            project=project,
            description=description,
            assignee=assignee,
            priority=priority,
            labels=labels or [],
        )
        self._issues[key] = issue
        self._projects[project] = Project(
            key=project,
            name=self._projects[project].name,
            lead=self._projects[project].lead,
            issue_count=self._projects[project].issue_count + 1,
        )
        return issue

    def get_issue(self, key: str) -> Issue:
        """Retrieve an issue by key. Raises KeyError if not found."""
        if key not in self._issues:
            raise KeyError(f"Issue {key} not found")
        return self._issues[key]

    def update_issue(self, key: str, **fields: Any) -> Issue:
        """Update fields on an existing issue. Returns updated issue."""
        old = self.get_issue(key)
        updates = {
            "key": old.key,
            "summary": fields.get("summary", old.summary),
            "issue_type": fields.get("issue_type", old.issue_type),
            "project": old.project,
            "status": fields.get("status", old.status),
            "description": fields.get("description", old.description),
            "assignee": fields.get("assignee", old.assignee),
            "priority": fields.get("priority", old.priority),
            "labels": fields.get("labels", list(old.labels)),
            "created_at": old.created_at,
            "updated_at": time.time(),
        }
        issue = Issue(**updates)
        self._issues[key] = issue
        return issue

    def delete_issue(self, key: str) -> None:
        """Delete an issue by key."""
        if key not in self._issues:
            raise KeyError(f"Issue {key} not found")
        del self._issues[key]

    def search_jql(self, jql: str, max_results: int = 50, start_at: int = 0) -> list[Issue]:
        """Search issues with a simplified JQL-like filter.

        Supports:
          project = PROJ
          status = "In Progress"
          type = Bug
          assignee = alice
          text ~ keyword  (substring match on summary)
        Multiple clauses joined by AND.
        """
        issues = list(self._issues.values())
        clauses = [c.strip() for c in jql.split(" AND ") if c.strip()]
        for clause in clauses:
            issues = self._apply_clause(issues, clause)
        # pagination
        return issues[start_at: start_at + max_results]

    def _apply_clause(self, issues: list[Issue], clause: str) -> list[Issue]:
        """Apply a single JQL clause as a filter."""
        if "~" in clause:
            parts = clause.split("~", 1)
            keyword = parts[1].strip().strip('"').strip("'").lower()
            return [i for i in issues if keyword in i.summary.lower()]
        if "=" in clause:
            parts = clause.split("=", 1)
            field_name = parts[0].strip().lower()
            value = parts[1].strip().strip('"').strip("'")
            if field_name == "project":
                return [i for i in issues if i.project == value]
            if field_name == "status":
                return [i for i in issues if i.status == value]
            if field_name == "type":
                return [i for i in issues if i.issue_type == value]
            if field_name == "assignee":
                return [i for i in issues if i.assignee == value]
        return issues

    def all_issues(self) -> list[Issue]:
        """Return all issues."""
        return list(self._issues.values())
