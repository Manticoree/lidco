"""IssueTracker — create/update Linear issues from code context.

Bridges code changes and git branches to Linear issue state.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from lidco.linear.client import Issue, LinearClient


@dataclass
class PRLink:
    """Association between an issue and a pull request URL."""

    issue_id: str
    pr_url: str


class IssueTracker:
    """Create and update Linear issues from code context."""

    def __init__(self, client: LinearClient | None = None) -> None:
        self._client = client or LinearClient()
        self._pr_links: dict[str, list[str]] = {}  # issue_id -> [pr_urls]

    @property
    def client(self) -> LinearClient:
        return self._client

    def create_from_code(
        self,
        title: str,
        file: str,
        *,
        team: str = "Engineering",
        description: str = "",
    ) -> Issue:
        """Create an issue linked to a source file.

        The file path is appended to the description for traceability.
        """
        desc = f"{description}\n\nSource: `{file}`".strip()
        return self._client.create_issue(title, team, description=desc)

    def link_pr(self, issue_id: str, pr_url: str) -> None:
        """Link a pull request URL to an issue.

        Raises:
            KeyError: If the issue does not exist.
        """
        # Verify issue exists
        self._client.get_issue(issue_id)
        self._pr_links.setdefault(issue_id, [])
        if pr_url not in self._pr_links[issue_id]:
            self._pr_links[issue_id].append(pr_url)

    def get_pr_links(self, issue_id: str) -> list[str]:
        """Return PR URLs linked to an issue."""
        return list(self._pr_links.get(issue_id, []))

    def update_status(self, issue_id: str, status: str) -> Issue:
        """Update the status of an issue.

        Valid statuses: Todo, In Progress, In Review, Done, Cancelled.

        Raises:
            ValueError: If the status is invalid.
            KeyError: If the issue does not exist.
        """
        valid = {"Todo", "In Progress", "In Review", "Done", "Cancelled"}
        if status not in valid:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {sorted(valid)}"
            )
        return self._client.update_issue(issue_id, status=status)

    def auto_status(self, git_branch: str) -> str:
        """Infer a Linear status from a git branch name.

        Convention:
        - feature/* or feat/* -> In Progress
        - fix/* or bugfix/* -> In Progress
        - review/* or pr/* -> In Review
        - main, master, release/* -> Done
        - anything else -> Todo
        """
        branch = git_branch.strip()
        if re.match(r"^(feature|feat|fix|bugfix)/", branch):
            return "In Progress"
        if re.match(r"^(review|pr)/", branch):
            return "In Review"
        if branch in ("main", "master") or branch.startswith("release/"):
            return "Done"
        return "Todo"
