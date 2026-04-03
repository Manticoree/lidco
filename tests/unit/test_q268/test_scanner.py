"""Tests for DLPScanner."""
from __future__ import annotations

import unittest

from lidco.dlp.scanner import DLPFinding, DLPScanResult, DLPScanner


class TestDLPFinding(unittest.TestCase):
    def test_frozen(self):
        f = DLPFinding(type="pii", severity="high", match="te**st", position=0)
        with self.assertRaises(AttributeError):
            f.type = "credential"  # type: ignore[misc]

    def test_default_context(self):
        f = DLPFinding(type="pii", severity="low", match="x", position=0)
        self.assertEqual(f.context, "")


class TestDLPScanResult(unittest.TestCase):
    def test_frozen(self):
        r = DLPScanResult(findings=[], blocked=False, total_scanned=0, recommendation="ok")
        with self.assertRaises(AttributeError):
            r.blocked = True  # type: ignore[misc]


class TestDLPScanner(unittest.TestCase):
    def test_scan_clean(self):
        scanner = DLPScanner()
        result = scanner.scan("Hello world, nothing sensitive here.")
        self.assertFalse(result.blocked)
        self.assertEqual(len(result.findings), 0)
        self.assertIn("No sensitive data", result.recommendation)

    def test_scan_email(self):
        scanner = DLPScanner()
        result = scanner.scan("Contact us at user@example.com for info.")
        self.assertTrue(any(f.type == "pii" for f in result.findings))

    def test_scan_ssn(self):
        scanner = DLPScanner()
        result = scanner.scan("SSN: 123-45-6789")
        self.assertTrue(result.blocked)
        self.assertTrue(any(f.severity == "critical" for f in result.findings))

    def test_scan_aws_key(self):
        scanner = DLPScanner()
        result = scanner.scan("key=AKIAIOSFODNN7EXAMPLE")
        self.assertTrue(any(f.type == "credential" for f in result.findings))

    def test_scan_sk_key(self):
        scanner = DLPScanner()
        result = scanner.scan("token: sk-abcdefghijklmnopqrstuvwx")
        self.assertTrue(any(f.type == "credential" for f in result.findings))

    def test_scan_private_key(self):
        scanner = DLPScanner()
        result = scanner.scan("-----BEGIN RSA PRIVATE KEY-----\ndata\n-----END RSA PRIVATE KEY-----")
        self.assertTrue(any(f.severity == "critical" for f in result.findings))

    def test_scan_jwt(self):
        scanner = DLPScanner()
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123def456ghi789jklmno"
        result = scanner.scan(f"token={jwt}")
        self.assertTrue(any(f.type == "credential" for f in result.findings))

    def test_should_block_low_threshold(self):
        scanner = DLPScanner(block_threshold="low")
        result = scanner.scan("Contact user@example.com")
        self.assertTrue(scanner.should_block(result))

    def test_add_pattern(self):
        scanner = DLPScanner()
        scanner.add_pattern("custom", r"SECRET-\d+", "critical")
        result = scanner.scan("SECRET-12345")
        self.assertTrue(any(f.severity == "critical" for f in result.findings))

    def test_patterns_returns_dict(self):
        scanner = DLPScanner()
        pats = scanner.patterns()
        self.assertIn("email", pats)
        self.assertIsInstance(pats, dict)

    def test_summary(self):
        scanner = DLPScanner()
        scanner.scan("test@test.com")
        s = scanner.summary()
        self.assertEqual(s["total_scans"], 1)
        self.assertGreater(s["pattern_count"], 0)


if __name__ == "__main__":
    unittest.main()
