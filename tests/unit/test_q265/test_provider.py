"""Tests for Q265 IdentityProvider / LocalIdentityProvider."""
from __future__ import annotations

import unittest

from lidco.identity.provider import LocalIdentityProvider, UserInfo


class TestLocalIdentityProvider(unittest.TestCase):
    def _make(self) -> LocalIdentityProvider:
        return LocalIdentityProvider()

    def test_add_user(self):
        p = self._make()
        info = p.add_user("alice", "pass123", email="alice@example.com")
        assert isinstance(info, UserInfo)
        assert info.username == "alice"
        assert info.email == "alice@example.com"

    def test_add_user_with_groups(self):
        p = self._make()
        info = p.add_user("bob", "pw", groups=["admin", "dev"])
        assert info.groups == ["admin", "dev"]

    def test_authenticate_success(self):
        p = self._make()
        p.add_user("alice", "secret")
        result = p.authenticate("alice", "secret")
        assert result is not None
        assert result.username == "alice"

    def test_authenticate_wrong_password(self):
        p = self._make()
        p.add_user("alice", "secret")
        assert p.authenticate("alice", "wrong") is None

    def test_authenticate_unknown_user(self):
        p = self._make()
        assert p.authenticate("nobody", "pw") is None

    def test_password_is_hashed(self):
        p = self._make()
        info = p.add_user("alice", "plaintext")
        stored = p._passwords[info.user_id]
        assert stored != "plaintext"
        assert len(stored) == 64  # sha256 hex digest

    def test_get_user(self):
        p = self._make()
        info = p.add_user("alice", "pw")
        assert p.get_user(info.user_id) == info

    def test_get_user_not_found(self):
        p = self._make()
        assert p.get_user("nonexistent") is None

    def test_list_users(self):
        p = self._make()
        p.add_user("alice", "pw1")
        p.add_user("bob", "pw2")
        assert len(p.list_users()) == 2

    def test_remove_user(self):
        p = self._make()
        info = p.add_user("alice", "pw")
        assert p.remove_user(info.user_id) is True
        assert p.get_user(info.user_id) is None
        assert p.authenticate("alice", "pw") is None

    def test_remove_user_not_found(self):
        p = self._make()
        assert p.remove_user("bogus") is False

    def test_summary(self):
        p = self._make()
        p.add_user("alice", "pw")
        s = p.summary()
        assert s["total_users"] == 1
        assert "alice" in s["usernames"]


if __name__ == "__main__":
    unittest.main()
