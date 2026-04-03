"""Tests for SessionAuth (Q259)."""
from __future__ import annotations

import time
import unittest

from lidco.rbac.session_auth import AuthToken, SessionAuth


class TestAuthToken(unittest.TestCase):
    def test_fields(self):
        t = AuthToken(
            token="abc", user="alice", role="admin",
            created_at=1.0, expires_at=2.0,
        )
        self.assertEqual(t.token, "abc")
        self.assertIsNone(t.refreshed_at)


class TestSessionAuth(unittest.TestCase):
    def setUp(self):
        self.auth = SessionAuth(token_ttl=3600.0)

    def test_create_token(self):
        token = self.auth.create_token("alice", "admin")
        self.assertEqual(token.user, "alice")
        self.assertEqual(token.role, "admin")
        self.assertEqual(len(token.token), 48)

    def test_validate_valid(self):
        token = self.auth.create_token("bob")
        result = self.auth.validate(token.token)
        self.assertIsNotNone(result)
        self.assertEqual(result.user, "bob")

    def test_validate_invalid(self):
        self.assertIsNone(self.auth.validate("nonexistent"))

    def test_validate_expired(self):
        auth = SessionAuth(token_ttl=0.0)
        token = auth.create_token("alice")
        # Token expired immediately
        time.sleep(0.01)
        self.assertIsNone(auth.validate(token.token))

    def test_refresh(self):
        token = self.auth.create_token("alice")
        original_expires = token.expires_at
        time.sleep(0.01)
        refreshed = self.auth.refresh(token.token)
        self.assertIsNotNone(refreshed)
        self.assertGreaterEqual(refreshed.expires_at, original_expires)
        self.assertIsNotNone(refreshed.refreshed_at)

    def test_refresh_invalid(self):
        self.assertIsNone(self.auth.refresh("bogus"))

    def test_revoke(self):
        token = self.auth.create_token("alice")
        self.assertTrue(self.auth.revoke(token.token))
        self.assertIsNone(self.auth.validate(token.token))

    def test_revoke_nonexistent(self):
        self.assertFalse(self.auth.revoke("ghost"))

    def test_active_sessions(self):
        self.auth.create_token("a")
        self.auth.create_token("b")
        active = self.auth.active_sessions()
        self.assertEqual(len(active), 2)

    def test_active_sessions_filters_expired(self):
        auth = SessionAuth(token_ttl=0.0)
        auth.create_token("expired_user")
        time.sleep(0.01)
        active = auth.active_sessions()
        self.assertEqual(len(active), 0)

    def test_cleanup_expired(self):
        auth = SessionAuth(token_ttl=0.0)
        auth.create_token("a")
        auth.create_token("b")
        time.sleep(0.01)
        removed = auth.cleanup_expired()
        self.assertEqual(removed, 2)

    def test_summary(self):
        self.auth.create_token("x")
        s = self.auth.summary()
        self.assertEqual(s["total_tokens"], 1)
        self.assertEqual(s["ttl"], 3600.0)


if __name__ == "__main__":
    unittest.main()
