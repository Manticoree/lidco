"""Tests for CertificateManager (Q263)."""
from __future__ import annotations

import unittest

from lidco.netsec.certificates import CertInfo, CertificateManager

_SAMPLE_PEM = """\
-----BEGIN CERTIFICATE-----
Subject: CN=example.com
Issuer: CN=My CA
Not Before: 2025-01-01
Not After: 2027-12-31
MIIB...base64data...
-----END CERTIFICATE-----
"""

_EXPIRED_PEM = """\
-----BEGIN CERTIFICATE-----
Subject: CN=old.example.com
Issuer: CN=Old CA
Not Before: 2020-01-01
Not After: 2023-12-31
MIIB...expired...
-----END CERTIFICATE-----
"""


class TestCertInfo(unittest.TestCase):
    def test_frozen(self):
        info = CertInfo(subject="CN=x", issuer="CN=y", not_before="", not_after="", fingerprint="abc")
        with self.assertRaises(AttributeError):
            info.subject = "other"  # type: ignore[misc]

    def test_defaults(self):
        info = CertInfo(subject="", issuer="", not_before="", not_after="", fingerprint="")
        self.assertFalse(info.is_expired)


class TestRegister(unittest.TestCase):
    def test_register_and_get(self):
        mgr = CertificateManager()
        info = mgr.register("test", _SAMPLE_PEM)
        self.assertEqual(info.subject, "CN=example.com")
        self.assertEqual(info.issuer, "CN=My CA")
        self.assertFalse(info.is_expired)
        retrieved = mgr.get("test")
        self.assertEqual(retrieved, info)

    def test_register_expired(self):
        mgr = CertificateManager()
        info = mgr.register("old", _EXPIRED_PEM)
        self.assertTrue(info.is_expired)

    def test_get_nonexistent(self):
        mgr = CertificateManager()
        self.assertIsNone(mgr.get("nope"))


class TestRemove(unittest.TestCase):
    def test_remove_existing(self):
        mgr = CertificateManager()
        mgr.register("test", _SAMPLE_PEM)
        self.assertTrue(mgr.remove("test"))
        self.assertIsNone(mgr.get("test"))

    def test_remove_nonexistent(self):
        mgr = CertificateManager()
        self.assertFalse(mgr.remove("nope"))


class TestCheckExpiry(unittest.TestCase):
    def test_check_expiry(self):
        mgr = CertificateManager()
        mgr.register("valid", _SAMPLE_PEM)
        mgr.register("old", _EXPIRED_PEM)
        expired = mgr.check_expiry()
        names = [n for n, _ in expired]
        self.assertIn("old", names)
        self.assertNotIn("valid", names)


class TestFingerprint(unittest.TestCase):
    def test_deterministic(self):
        mgr = CertificateManager()
        fp1 = mgr.fingerprint("hello")
        fp2 = mgr.fingerprint("hello")
        self.assertEqual(fp1, fp2)

    def test_different_content(self):
        mgr = CertificateManager()
        self.assertNotEqual(mgr.fingerprint("a"), mgr.fingerprint("b"))


class TestAllCerts(unittest.TestCase):
    def test_all_certs(self):
        mgr = CertificateManager()
        mgr.register("a", _SAMPLE_PEM)
        mgr.register("b", _EXPIRED_PEM)
        certs = mgr.all_certs()
        self.assertEqual(len(certs), 2)
        self.assertIn("a", certs)
        self.assertIn("b", certs)


class TestSummary(unittest.TestCase):
    def test_summary(self):
        mgr = CertificateManager()
        mgr.register("valid", _SAMPLE_PEM)
        mgr.register("old", _EXPIRED_PEM)
        s = mgr.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["expired"], 1)
        self.assertEqual(s["valid"], 1)


if __name__ == "__main__":
    unittest.main()
