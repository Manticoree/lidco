"""Tests for lidco.teams.registry."""

from __future__ import annotations

import pytest

from lidco.teams.registry import (
    Team,
    TeamMember,
    TeamNotFoundError,
    TeamRegistry,
    TeamRole,
)


class TestTeamRole:
    def test_enum_values(self) -> None:
        assert TeamRole.OWNER == "owner"
        assert TeamRole.EDITOR == "editor"
        assert TeamRole.VIEWER == "viewer"


class TestTeamMemberFrozen:
    def test_frozen(self) -> None:
        m = TeamMember(user_id="u1", role=TeamRole.VIEWER, joined_at=1.0)
        with pytest.raises(AttributeError):
            m.user_id = "u2"  # type: ignore[misc]


class TestTeamRegistry:
    def test_create_team_basic(self) -> None:
        reg = TeamRegistry()
        team = reg.create_team("alpha")
        assert team.name == "alpha"
        assert len(team.id) == 8
        assert team.members == ()
        assert reg.team_count() == 1

    def test_create_team_with_owner(self) -> None:
        reg = TeamRegistry()
        team = reg.create_team("beta", owner_id="alice")
        assert len(team.members) == 1
        assert team.members[0].user_id == "alice"
        assert team.members[0].role == TeamRole.OWNER

    def test_delete_team(self) -> None:
        reg = TeamRegistry()
        team = reg.create_team("x")
        assert reg.delete_team(team.id) is True
        assert reg.delete_team(team.id) is False
        assert reg.team_count() == 0

    def test_get_team(self) -> None:
        reg = TeamRegistry()
        team = reg.create_team("y")
        assert reg.get_team(team.id) is not None
        assert reg.get_team("missing") is None

    def test_list_teams(self) -> None:
        reg = TeamRegistry()
        reg.create_team("a")
        reg.create_team("b")
        assert len(reg.list_teams()) == 2

    def test_add_member(self) -> None:
        reg = TeamRegistry()
        team = reg.create_team("t")
        updated = reg.add_member(team.id, "bob", TeamRole.EDITOR)
        assert len(updated.members) == 1
        assert updated.members[0].role == TeamRole.EDITOR

    def test_add_member_duplicate_ignored(self) -> None:
        reg = TeamRegistry()
        team = reg.create_team("t")
        reg.add_member(team.id, "bob")
        updated = reg.add_member(team.id, "bob")
        assert len(updated.members) == 1

    def test_add_member_team_not_found(self) -> None:
        reg = TeamRegistry()
        with pytest.raises(TeamNotFoundError):
            reg.add_member("missing", "bob")

    def test_remove_member(self) -> None:
        reg = TeamRegistry()
        team = reg.create_team("t", owner_id="alice")
        updated = reg.remove_member(team.id, "alice")
        assert len(updated.members) == 0

    def test_get_member_role(self) -> None:
        reg = TeamRegistry()
        team = reg.create_team("t", owner_id="alice")
        assert reg.get_member_role(team.id, "alice") == TeamRole.OWNER
        assert reg.get_member_role(team.id, "nobody") is None
        assert reg.get_member_role("missing", "alice") is None

    def test_search(self) -> None:
        reg = TeamRegistry()
        reg.create_team("Frontend", description="UI work")
        reg.create_team("Backend", description="API work")
        results = reg.search("front")
        assert len(results) == 1
        assert results[0].name == "Frontend"

    def test_search_by_description(self) -> None:
        reg = TeamRegistry()
        reg.create_team("Team1", description="handles billing")
        results = reg.search("billing")
        assert len(results) == 1
