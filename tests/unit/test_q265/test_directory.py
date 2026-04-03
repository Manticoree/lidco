"""Tests for Q265 UserDirectory."""
from __future__ import annotations

import unittest

from lidco.identity.directory import Group, UserDirectory, UserProfile


class TestUserDirectory(unittest.TestCase):
    def _make(self) -> UserDirectory:
        return UserDirectory()

    def test_add_user(self):
        d = self._make()
        p = d.add_user("alice", email="alice@ex.com", display_name="Alice")
        assert isinstance(p, UserProfile)
        assert p.username == "alice"
        assert p.email == "alice@ex.com"
        assert p.active is True

    def test_get_user(self):
        d = self._make()
        p = d.add_user("alice")
        assert d.get_user(p.user_id) is p

    def test_get_user_not_found(self):
        d = self._make()
        assert d.get_user("nope") is None

    def test_find_by_username(self):
        d = self._make()
        p = d.add_user("alice")
        assert d.find_by_username("alice") is p

    def test_find_by_username_not_found(self):
        d = self._make()
        assert d.find_by_username("nope") is None

    def test_remove_user(self):
        d = self._make()
        p = d.add_user("alice")
        assert d.remove_user(p.user_id) is True
        assert d.get_user(p.user_id) is None

    def test_remove_user_not_found(self):
        d = self._make()
        assert d.remove_user("bogus") is False

    def test_create_group(self):
        d = self._make()
        g = d.create_group("admins", description="Admin group", permissions=["read", "write"])
        assert isinstance(g, Group)
        assert g.name == "admins"
        assert g.permissions == ["read", "write"]

    def test_add_to_group(self):
        d = self._make()
        p = d.add_user("alice")
        d.create_group("devs", permissions=["code"])
        assert d.add_to_group(p.user_id, "devs") is True
        assert "devs" in p.groups

    def test_add_to_group_unknown_group(self):
        d = self._make()
        p = d.add_user("alice")
        assert d.add_to_group(p.user_id, "nosuch") is False

    def test_add_to_group_unknown_user(self):
        d = self._make()
        d.create_group("devs")
        assert d.add_to_group("fake-id", "devs") is False

    def test_add_to_group_idempotent(self):
        d = self._make()
        p = d.add_user("alice")
        d.create_group("devs")
        d.add_to_group(p.user_id, "devs")
        d.add_to_group(p.user_id, "devs")
        assert p.groups.count("devs") == 1

    def test_remove_from_group(self):
        d = self._make()
        p = d.add_user("alice")
        d.create_group("devs")
        d.add_to_group(p.user_id, "devs")
        assert d.remove_from_group(p.user_id, "devs") is True
        assert "devs" not in p.groups

    def test_remove_from_group_not_member(self):
        d = self._make()
        p = d.add_user("alice")
        d.create_group("devs")
        assert d.remove_from_group(p.user_id, "devs") is False

    def test_user_permissions(self):
        d = self._make()
        p = d.add_user("alice")
        d.create_group("readers", permissions=["read"])
        d.create_group("writers", permissions=["write", "read"])
        d.add_to_group(p.user_id, "readers")
        d.add_to_group(p.user_id, "writers")
        perms = d.user_permissions(p.user_id)
        assert perms == {"read", "write"}

    def test_user_permissions_unknown_user(self):
        d = self._make()
        assert d.user_permissions("nope") == set()

    def test_group_members(self):
        d = self._make()
        p1 = d.add_user("alice")
        p2 = d.add_user("bob")
        d.create_group("team")
        d.add_to_group(p1.user_id, "team")
        d.add_to_group(p2.user_id, "team")
        members = d.group_members("team")
        assert len(members) == 2

    def test_group_members_unknown_group(self):
        d = self._make()
        assert d.group_members("nope") == []

    def test_all_users_active_only(self):
        d = self._make()
        p1 = d.add_user("alice")
        p2 = d.add_user("bob")
        p2.active = False
        active = d.all_users()
        assert len(active) == 1
        assert active[0].username == "alice"

    def test_all_users_include_inactive(self):
        d = self._make()
        d.add_user("alice")
        p2 = d.add_user("bob")
        p2.active = False
        assert len(d.all_users(include_inactive=True)) == 2

    def test_all_groups(self):
        d = self._make()
        d.create_group("g1")
        d.create_group("g2")
        assert len(d.all_groups()) == 2

    def test_summary(self):
        d = self._make()
        d.add_user("alice")
        d.create_group("devs")
        s = d.summary()
        assert s["total_users"] == 1
        assert s["total_groups"] == 1

    def test_remove_user_cleans_group_membership(self):
        d = self._make()
        p = d.add_user("alice")
        d.create_group("team")
        d.add_to_group(p.user_id, "team")
        d.remove_user(p.user_id)
        assert d.group_members("team") == []


if __name__ == "__main__":
    unittest.main()
