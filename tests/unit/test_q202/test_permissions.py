"""Tests for lidco.teams.permissions."""

from __future__ import annotations

from lidco.teams.permissions import PermissionRule, TeamPermissions


class TestPermissionRule:
    def test_defaults(self) -> None:
        rule = PermissionRule(tool_name="read")
        assert rule.allowed is True
        assert rule.scope == "team"


class TestTeamPermissions:
    def test_allow(self) -> None:
        tp = TeamPermissions("t1")
        tp.allow("read")
        assert tp.is_allowed("read") is True

    def test_deny(self) -> None:
        tp = TeamPermissions("t1")
        tp.deny("write")
        assert tp.is_allowed("write") is False

    def test_default_allowed(self) -> None:
        tp = TeamPermissions("t1")
        assert tp.is_allowed("anything") is True

    def test_parent_inheritance(self) -> None:
        parent = TeamPermissions("org")
        parent.deny("deploy")
        child = TeamPermissions("t1")
        assert child.is_allowed("deploy", parent_permissions=parent) is False

    def test_child_overrides_parent(self) -> None:
        parent = TeamPermissions("org")
        parent.deny("deploy")
        child = TeamPermissions("t1")
        child.allow("deploy")
        assert child.is_allowed("deploy", parent_permissions=parent) is True

    def test_list_rules(self) -> None:
        tp = TeamPermissions("t1")
        tp.allow("read")
        tp.deny("write")
        rules = tp.list_rules()
        assert len(rules) == 2
        names = {r.tool_name for r in rules}
        assert names == {"read", "write"}

    def test_clear(self) -> None:
        tp = TeamPermissions("t1")
        tp.allow("read")
        tp.clear()
        assert tp.list_rules() == []

    def test_merge(self) -> None:
        a = TeamPermissions("t1")
        a.allow("read")
        a.deny("write")
        b = TeamPermissions("t1")
        b.allow("write")
        b.deny("delete")
        merged = a.merge(b)
        assert merged.is_allowed("read") is True
        assert merged.is_allowed("write") is True  # b overrides a
        assert merged.is_allowed("delete") is False
