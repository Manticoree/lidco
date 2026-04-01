"""Tests for teleport.share."""
from __future__ import annotations

import time
import unittest

from lidco.teleport.share import ShareLink, ShareManager


class TestShareLink(unittest.TestCase):
    def test_frozen(self) -> None:
        link = ShareLink(id="x", session_id="s1")
        with self.assertRaises(AttributeError):
            link.id = "y"  # type: ignore[misc]

    def test_defaults(self) -> None:
        link = ShareLink(id="x", session_id="s1")
        self.assertEqual(link.expires_at, 0.0)
        self.assertEqual(link.access_count, 0)
        self.assertFalse(link.anonymized)
        self.assertIsInstance(link.created_at, float)


class TestShareManager(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = ShareManager(default_expiry=3600.0)

    def test_create_share_basic(self) -> None:
        link = self.mgr.create_share("s1", "content here")
        self.assertEqual(link.session_id, "s1")
        self.assertFalse(link.anonymized)
        self.assertGreater(link.expires_at, 0.0)

    def test_create_share_anonymized(self) -> None:
        link = self.mgr.create_share("s1", "key=sk-abc123def456ghij", anonymize=True)
        self.assertTrue(link.anonymized)

    def test_anonymize_api_key(self) -> None:
        text = "My key is sk-proj-abcdefghijklmnop and done"
        result = self.mgr.anonymize(text)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("sk-proj", result)

    def test_anonymize_email(self) -> None:
        text = "Contact user@example.com for details"
        result = self.mgr.anonymize(text)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("user@example.com", result)

    def test_anonymize_bearer_token(self) -> None:
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9"
        result = self.mgr.anonymize(text)
        self.assertIn("[REDACTED]", result)

    def test_is_expired_false(self) -> None:
        link = self.mgr.create_share("s1", "x")
        self.assertFalse(self.mgr.is_expired(link))

    def test_is_expired_true(self) -> None:
        link = ShareLink(id="x", session_id="s1", expires_at=time.time() - 100)
        self.assertTrue(self.mgr.is_expired(link))

    def test_get_shares(self) -> None:
        self.mgr.create_share("s1", "a")
        self.mgr.create_share("s2", "b")
        self.assertEqual(len(self.mgr.get_shares()), 2)

    def test_revoke(self) -> None:
        link = self.mgr.create_share("s1", "x")
        self.assertTrue(self.mgr.revoke(link.id))
        self.assertEqual(len(self.mgr.get_shares()), 0)

    def test_revoke_nonexistent(self) -> None:
        self.assertFalse(self.mgr.revoke("no-such-id"))

    def test_summary(self) -> None:
        self.mgr.create_share("s1", "data")
        s = self.mgr.summary()
        self.assertIn("1 active", s)
