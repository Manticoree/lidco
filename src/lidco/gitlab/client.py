"""
GitLab API client (simulated) for LIDCO.

Provides project listing, user info, and paginated API access.
All calls are simulated — no real HTTP requests are made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GitLabProject:
    """Represents a GitLab project."""

    id: int
    name: str
    path_with_namespace: str
    default_branch: str = "main"
    web_url: str = ""


class GitLabClient:
    """Simulated GitLab REST API client."""

    def __init__(self, token: str = "", base_url: str = "https://gitlab.com") -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._projects: dict[int, dict[str, Any]] = {}
        self._next_id = 1

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def token(self) -> str:
        return self._token

    def get_project(self, project_id: int) -> dict[str, Any]:
        """Return project dict by ID, or raise KeyError."""
        if project_id not in self._projects:
            raise KeyError(f"Project {project_id} not found")
        return dict(self._projects[project_id])

    def list_projects(self, group: str = "") -> list[dict[str, Any]]:
        """List projects, optionally filtered by group prefix."""
        results = []
        for proj in self._projects.values():
            if group and not proj.get("path_with_namespace", "").startswith(group):
                continue
            results.append(dict(proj))
        return results

    def get_user(self) -> dict[str, Any]:
        """Return the authenticated user info (simulated)."""
        if not self._token:
            raise PermissionError("No token configured")
        return {
            "id": 1,
            "username": "lidco-bot",
            "name": "LIDCO Bot",
            "email": "lidco@example.com",
            "state": "active",
        }

    def paginate(self, url: str) -> list[dict[str, Any]]:
        """Simulate paginated API response for a given URL path."""
        if not url:
            raise ValueError("URL must not be empty")
        # Simulated: return projects as a generic paginated result
        return list(self._projects.values())

    # -- helpers for simulated state --

    def _add_project(
        self,
        name: str,
        namespace: str = "group",
        default_branch: str = "main",
    ) -> dict[str, Any]:
        """Add a simulated project and return its dict."""
        pid = self._next_id
        self._next_id += 1
        proj: dict[str, Any] = {
            "id": pid,
            "name": name,
            "path_with_namespace": f"{namespace}/{name}",
            "default_branch": default_branch,
            "web_url": f"{self._base_url}/{namespace}/{name}",
        }
        self._projects[pid] = proj
        return proj
