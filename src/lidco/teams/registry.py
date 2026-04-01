"""Team registry — team management with member roles."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TeamRole(str, Enum):
    """Role a member can hold within a team."""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class TeamError(Exception):
    """Base error for team operations."""


class TeamNotFoundError(TeamError):
    """Raised when a team cannot be found."""


@dataclass(frozen=True)
class TeamMember:
    """An individual team member."""

    user_id: str
    role: TeamRole
    joined_at: float


@dataclass(frozen=True)
class Team:
    """A named team with members."""

    id: str
    name: str
    description: str = ""
    members: tuple[TeamMember, ...] = ()
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class TeamRegistry:
    """Manages teams, membership, and lookup."""

    def __init__(self) -> None:
        self._teams: dict[str, Team] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_team(self, name: str, description: str = "", owner_id: str = "") -> Team:
        """Create a new team, optionally with an owner."""
        team_id = uuid.uuid4().hex[:8]
        members: tuple[TeamMember, ...] = ()
        if owner_id:
            members = (TeamMember(user_id=owner_id, role=TeamRole.OWNER, joined_at=time.time()),)
        team = Team(
            id=team_id,
            name=name,
            description=description,
            members=members,
            created_at=time.time(),
        )
        self._teams[team_id] = team
        return team

    def delete_team(self, team_id: str) -> bool:
        """Delete a team by ID. Returns True if deleted."""
        return self._teams.pop(team_id, None) is not None

    def get_team(self, team_id: str) -> Team | None:
        """Return a team or None."""
        return self._teams.get(team_id)

    def list_teams(self) -> list[Team]:
        """Return all teams."""
        return list(self._teams.values())

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    def add_member(self, team_id: str, user_id: str, role: TeamRole = TeamRole.VIEWER) -> Team:
        """Add a member to a team. Returns updated team."""
        team = self._teams.get(team_id)
        if team is None:
            raise TeamNotFoundError(f"Team '{team_id}' not found")
        # Prevent duplicate
        for m in team.members:
            if m.user_id == user_id:
                return team
        new_member = TeamMember(user_id=user_id, role=role, joined_at=time.time())
        updated = Team(
            id=team.id,
            name=team.name,
            description=team.description,
            members=team.members + (new_member,),
            created_at=team.created_at,
            metadata=dict(team.metadata),
        )
        self._teams[team_id] = updated
        return updated

    def remove_member(self, team_id: str, user_id: str) -> Team:
        """Remove a member from a team. Returns updated team."""
        team = self._teams.get(team_id)
        if team is None:
            raise TeamNotFoundError(f"Team '{team_id}' not found")
        updated = Team(
            id=team.id,
            name=team.name,
            description=team.description,
            members=tuple(m for m in team.members if m.user_id != user_id),
            created_at=team.created_at,
            metadata=dict(team.metadata),
        )
        self._teams[team_id] = updated
        return updated

    def get_member_role(self, team_id: str, user_id: str) -> TeamRole | None:
        """Return the role of a member, or None if not found."""
        team = self._teams.get(team_id)
        if team is None:
            return None
        for m in team.members:
            if m.user_id == user_id:
                return m.role
        return None

    # ------------------------------------------------------------------
    # Search / counts
    # ------------------------------------------------------------------

    def search(self, query: str) -> list[Team]:
        """Search teams by name or description (case-insensitive)."""
        q = query.lower()
        return [
            t for t in self._teams.values()
            if q in t.name.lower() or q in t.description.lower()
        ]

    def team_count(self) -> int:
        """Return the number of teams."""
        return len(self._teams)
