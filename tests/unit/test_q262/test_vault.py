"""Tests for VaultClient (Q262)."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.secrets.vault import VaultClient, VaultSecret


class TestVaultSecret(unittest.TestCase):
    def test_fields(self):
        s = VaultSecret(key="k", value="v", version=1, created_at=1.0)
        self.assertEqual(s.key, "k")
        self.assertEqual(s.version, 1)
        self.assertIsNone(s.expires_at)
        self.assertEqual(s.metadata, {})


class TestPutAndGet(unittest.TestCase):
    def test_put_creates_secret(self):
        vault = VaultClient()
        s = vault.put("api-key", "secret123")
        self.assertEqual(s.key, "api-key")
        self.assertEqual(s.value, "secret123")
        self.assertEqual(s.version, 1)

    def test_get_returns_latest(self):
        vault = VaultClient()
        vault.put("k", "v1")
        vault.put("k", "v2")
        s = vault.get("k")
        self.assertIsNotNone(s)
        self.assertEqual(s.value, "v2")
        self.assertEqual(s.version, 2)

    def test_get_nonexistent(self):
        vault = VaultClient()
        self.assertIsNone(vault.get("missing"))


class TestVersioning(unittest.TestCase):
    def test_multiple_versions(self):
        vault = VaultClient()
        vault.put("k", "v1")
        vault.put("k", "v2")
        vault.put("k", "v3")
        versions = vault.versions("k")
        self.assertEqual(len(versions), 3)
        self.assertEqual(versions[0].value, "v1")
        self.assertEqual(versions[2].value, "v3")

    def test_get_specific_version(self):
        vault = VaultClient()
        vault.put("k", "v1")
        vault.put("k", "v2")
        s = vault.get("k", version=1)
        self.assertIsNotNone(s)
        self.assertEqual(s.value, "v1")

    def test_get_missing_version(self):
        vault = VaultClient()
        vault.put("k", "v1")
        self.assertIsNone(vault.get("k", version=99))


class TestTTL(unittest.TestCase):
    def test_ttl_not_expired(self):
        vault = VaultClient()
        vault.put("k", "v", ttl=3600)
        s = vault.get("k")
        self.assertIsNotNone(s)

    def test_ttl_expired(self):
        vault = VaultClient()
        # Put with a very short TTL in the past
        s = vault.put("k", "v", ttl=0.0)
        # Force expires_at to past
        s.expires_at = time.time() - 10
        result = vault.get("k")
        self.assertIsNone(result)

    def test_expired_specific_version(self):
        vault = VaultClient()
        s = vault.put("k", "v", ttl=0.0)
        s.expires_at = time.time() - 10
        self.assertIsNone(vault.get("k", version=1))


class TestDelete(unittest.TestCase):
    def test_delete_existing(self):
        vault = VaultClient()
        vault.put("k", "v")
        self.assertTrue(vault.delete("k"))
        self.assertIsNone(vault.get("k"))

    def test_delete_nonexistent(self):
        vault = VaultClient()
        self.assertFalse(vault.delete("missing"))


class TestListKeys(unittest.TestCase):
    def test_list_all(self):
        vault = VaultClient()
        vault.put("app/db", "x")
        vault.put("app/api", "y")
        vault.put("other", "z")
        keys = vault.list_keys()
        self.assertEqual(keys, ["app/api", "app/db", "other"])

    def test_list_prefix(self):
        vault = VaultClient()
        vault.put("app/db", "x")
        vault.put("app/api", "y")
        vault.put("other", "z")
        keys = vault.list_keys("app/")
        self.assertEqual(keys, ["app/api", "app/db"])

    def test_list_excludes_expired(self):
        vault = VaultClient()
        s = vault.put("k", "v", ttl=0.0)
        s.expires_at = time.time() - 10
        self.assertEqual(vault.list_keys(), [])


class TestRenewLease(unittest.TestCase):
    def test_renew(self):
        vault = VaultClient()
        vault.put("k", "v", ttl=10)
        renewed = vault.renew_lease("k", 7200)
        self.assertIsNotNone(renewed)
        self.assertGreater(renewed.expires_at, time.time() + 7000)

    def test_renew_nonexistent(self):
        vault = VaultClient()
        self.assertIsNone(vault.renew_lease("missing", 100))


class TestExpired(unittest.TestCase):
    def test_expired_list(self):
        vault = VaultClient()
        s = vault.put("old", "v", ttl=0.0)
        s.expires_at = time.time() - 10
        vault.put("fresh", "v", ttl=9999)
        expired = vault.expired()
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].key, "old")


class TestSummary(unittest.TestCase):
    def test_summary(self):
        vault = VaultClient()
        vault.put("a", "1")
        vault.put("a", "2")
        vault.put("b", "3")
        s = vault.summary()
        self.assertEqual(s["backend"], "memory")
        self.assertEqual(s["keys"], 2)
        self.assertEqual(s["total_versions"], 3)


if __name__ == "__main__":
    unittest.main()
