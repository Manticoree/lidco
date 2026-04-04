"""GitHubClient — simulated GitHub API client.

No real HTTP calls; all responses are simulated for offline usage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RateLimitInfo:
    """Rate limit snapshot."""

    limit: int
    remaining: int
    reset_at: str


class GitHubClient:
    """Simulated GitHub REST API client."""

    def __init__(self, token: str = "") -> None:
        self._token = token

    # -- helpers ----------------------------------------------------------

    @property
    def authenticated(self) -> bool:
        return bool(self._token)

    # -- endpoints --------------------------------------------------------

    def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """Return simulated repository metadata."""
        if not owner or not repo:
            raise ValueError("owner and repo are required")
        return {
            "full_name": f"{owner}/{repo}",
            "owner": owner,
            "name": repo,
            "default_branch": "main",
            "private": False,
            "stars": 42,
            "forks": 7,
            "open_issues": 3,
        }

    def list_repos(self, org: str) -> list[dict[str, Any]]:
        """Return simulated list of repos for *org*."""
        if not org:
            raise ValueError("org is required")
        return [
            {"full_name": f"{org}/repo-alpha", "name": "repo-alpha", "private": False},
            {"full_name": f"{org}/repo-beta", "name": "repo-beta", "private": True},
        ]

    def get_user(self) -> dict[str, Any]:
        """Return simulated authenticated user info."""
        return {
            "login": "lidco-bot",
            "id": 12345,
            "name": "LIDCO Bot",
            "email": "bot@lidco.dev",
        }

    def rate_limit(self) -> dict[str, Any]:
        """Return simulated rate limit info."""
        return {
            "limit": 5000,
            "remaining": 4990,
            "reset_at": "2026-04-04T12:00:00Z",
        }

    def paginate(self, url: str) -> list[dict[str, Any]]:
        """Simulate paginated API response for *url*."""
        if not url:
            raise ValueError("url is required")
        return [
            {"id": 1, "url": url, "page": 1},
            {"id": 2, "url": url, "page": 2},
        ]
