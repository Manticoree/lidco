"""AgentTeamRegistry — register and manage named agent teams."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentTeam:
    """A named team of agent roles."""

    name: str
    roles: dict[str, str]  # role_name -> agent_description
    mailbox: object = None  # AgentMailbox instance (injected)


class TeamNotFoundError(Exception):
    """Raised when a requested team does not exist."""


class AgentTeamRegistry:
    """Thread-safe registry for agent teams."""

    def __init__(self) -> None:
        self._teams: dict[str, AgentTeam] = {}
        self._lock = threading.Lock()

    def register(self, team: AgentTeam) -> None:
        """Register a team (idempotent -- same name overwrites)."""
        with self._lock:
            self._teams[team.name] = team

    def get(self, name: str) -> AgentTeam:
        """Retrieve a team by name. Raises TeamNotFoundError if missing."""
        with self._lock:
            if name not in self._teams:
                raise TeamNotFoundError(f"Team '{name}' not found")
            return self._teams[name]

    def list_all(self) -> list[AgentTeam]:
        """Return all registered teams."""
        with self._lock:
            return list(self._teams.values())

    def broadcast(self, team_name: str, message: str, sender: str = "coordinator") -> int:
        """Send message to all role members via team mailbox. Returns count of recipients."""
        team = self.get(team_name)
        if team.mailbox is None:
            return 0
        recipients = list(team.roles.keys())
        if not recipients:
            return 0
        team.mailbox.broadcast(from_=sender, message=message, recipients=recipients)
        return len(recipients)

    def unregister(self, name: str) -> None:
        """Remove a team from the registry."""
        with self._lock:
            if name not in self._teams:
                raise TeamNotFoundError(f"Team '{name}' not found")
            del self._teams[name]
