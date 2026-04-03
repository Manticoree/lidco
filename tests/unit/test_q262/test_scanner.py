"""Tests for SecretScanner (Q262)."""
from __future__ import annotations

import unittest

from lidco.secrets.scanner import SecretFinding, ScanResult, SecretScanner


class TestSecretFinding(unittest.TestCase):
    def test_frozen(self):
        f = SecretFinding("aws", "AKIA1234...", 1, 1, "critical", 0.9)
        with self.assertRaises(AttributeError):
            f.type = "other"  # type: ignore[misc]

    def test_fields(self):
        f = SecretFinding("jwt", "eyJhbGci...", 5, 10, "high", 0.85)
        self.assertEqual(f.type, "jwt")
        self.assertEqual(f.line, 5)
        self.assertEqual(f.severity, "high")


class TestScanResult(unittest.TestCase):
    def test_frozen(self):
        r = ScanResult(findings=[], scanned_lines=0)
        with self.assertRaises(AttributeError):
            r.scanned_lines = 5  # type: ignore[misc]

    def test_default_file_path(self):
        r = ScanResult(findings=[], scanned_lines=10)
        self.assertEqual(r.file_path, "")


class TestAWSKeyDetection(unittest.TestCase):
    def test_aws_access_key(self):
        scanner = SecretScanner()
        text = "aws_key = AKIAIOSFODNN7EXAMPLE"
        result = scanner.scan_text(text)
        types = [f.type for f in result.findings]
        self.assertIn("aws_access_key", types)

    def test_aws_secret_key(self):
        scanner = SecretScanner()
        text = "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        result = scanner.scan_text(text)
        types = [f.type for f in result.findings]
        self.assertIn("aws_secret_key", types)


class TestGitHubTokens(unittest.TestCase):
    def test_ghp_token(self):
        scanner = SecretScanner()
        text = "token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        result = scanner.scan_text(text)
        types = [f.type for f in result.findings]
        self.assertIn("github_pat", types)

    def test_gho_token(self):
        scanner = SecretScanner()
        text = "auth: gho_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        result = scanner.scan_text(text)
        types = [f.type for f in result.findings]
        self.assertIn("github_oauth", types)


class TestPrivateKeyDetection(unittest.TestCase):
    def test_rsa_private_key(self):
        scanner = SecretScanner()
        text = "-----BEGIN RSA PRIVATE KEY-----"
        result = scanner.scan_text(text)
        types = [f.type for f in result.findings]
        self.assertIn("private_key_rsa", types)

    def test_ec_private_key(self):
        scanner = SecretScanner()
        text = "-----BEGIN EC PRIVATE KEY-----"
        result = scanner.scan_text(text)
        types = [f.type for f in result.findings]
        self.assertIn("private_key_ec", types)


class TestJWTDetection(unittest.TestCase):
    def test_jwt_token(self):
        scanner = SecretScanner()
        text = "token = eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = scanner.scan_text(text)
        types = [f.type for f in result.findings]
        self.assertIn("jwt_token", types)


class TestPasswordDetection(unittest.TestCase):
    def test_password_in_code(self):
        scanner = SecretScanner()
        text = 'password = "SuperSecret123!"'
        result = scanner.scan_text(text)
        types = [f.type for f in result.findings]
        self.assertIn("password_assignment", types)


class TestEntropyDetection(unittest.TestCase):
    def test_high_entropy_hex(self):
        scanner = SecretScanner(entropy_threshold=3.5)
        text = "key = a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        result = scanner.scan_text(text)
        entropy_findings = [f for f in result.findings if f.type == "high_entropy_string"]
        self.assertTrue(len(entropy_findings) > 0)

    def test_low_entropy_skipped(self):
        scanner = SecretScanner(entropy_threshold=4.0)
        text = "key = aaaaaaaaaaaaaaaaaaaa"
        result = scanner.scan_text(text)
        entropy_findings = [f for f in result.findings if f.type == "high_entropy_string"]
        self.assertEqual(len(entropy_findings), 0)

    def test_calculate_entropy(self):
        scanner = SecretScanner()
        # All same chars -> entropy 0
        self.assertAlmostEqual(scanner._calculate_entropy("aaaa"), 0.0)
        # Two equally likely chars -> entropy 1.0
        self.assertAlmostEqual(scanner._calculate_entropy("ab"), 1.0)
        # Empty string -> 0
        self.assertEqual(scanner._calculate_entropy(""), 0.0)


class TestCustomPatterns(unittest.TestCase):
    def test_add_custom_pattern(self):
        scanner = SecretScanner(custom_patterns={"my_secret": r"MY_[A-Z]{10}"})
        text = "found MY_ABCDEFGHIJ here"
        result = scanner.scan_text(text)
        types = [f.type for f in result.findings]
        self.assertIn("my_secret", types)

    def test_add_pattern_method(self):
        scanner = SecretScanner()
        scanner.add_pattern("custom_xyz", r"XYZ_[0-9]{8}", severity="medium")
        text = "val = XYZ_12345678"
        result = scanner.scan_text(text)
        types = [f.type for f in result.findings]
        self.assertIn("custom_xyz", types)


class TestScannerMeta(unittest.TestCase):
    def test_patterns_property(self):
        scanner = SecretScanner()
        pats = scanner.patterns
        self.assertIn("aws_access_key", pats)
        self.assertIsInstance(pats["aws_access_key"], str)

    def test_summary(self):
        scanner = SecretScanner()
        scanner.scan_text("nothing here")
        s = scanner.summary()
        self.assertEqual(s["total_scans"], 1)
        self.assertGreaterEqual(s["pattern_count"], 30)

    def test_scan_lines(self):
        scanner = SecretScanner()
        result = scanner.scan_lines(["line one", "password = hunter2"], source="test.py")
        self.assertEqual(result.scanned_lines, 2)
        self.assertEqual(result.file_path, "test.py")
        self.assertTrue(len(result.findings) > 0)


if __name__ == "__main__":
    unittest.main()
