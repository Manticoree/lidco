"""Tests for sec_intel.secret_detector — SecretDetector, SecretFinding."""
from __future__ import annotations

import unittest

from lidco.sec_intel.secret_detector import SecretDetector, SecretFinding


class TestSecretFinding(unittest.TestCase):
    def test_frozen(self):
        f = SecretFinding(file="a.py", line=1, pattern_name="p", matched_text="x")
        with self.assertRaises(AttributeError):
            f.file = "b"  # type: ignore[misc]

    def test_defaults(self):
        f = SecretFinding(file="", line=0, pattern_name="p", matched_text="t")
        self.assertEqual(f.entropy, 0.0)
        self.assertEqual(f.false_positive_likelihood, "low")

    def test_equality(self):
        a = SecretFinding(file="f", line=1, pattern_name="p", matched_text="t")
        b = SecretFinding(file="f", line=1, pattern_name="p", matched_text="t")
        self.assertEqual(a, b)


class TestSecretDetectorPatterns(unittest.TestCase):
    def setUp(self):
        self.detector = SecretDetector()

    def test_aws_key(self):
        code = 'key = "AKIAIOSFODNN7EXAMPLE"'
        findings = self.detector.scan(code, "config.py")
        names = [f.pattern_name for f in findings]
        self.assertIn("aws-access-key", names)

    def test_github_token(self):
        code = 'token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"'
        findings = self.detector.scan(code)
        names = [f.pattern_name for f in findings]
        self.assertIn("github-token", names)

    def test_password_assignment(self):
        code = 'password = "mysecretpass"'
        findings = self.detector.scan(code)
        names = [f.pattern_name for f in findings]
        self.assertIn("password-assignment", names)

    def test_private_key(self):
        code = "-----BEGIN RSA PRIVATE KEY-----"
        findings = self.detector.scan(code)
        names = [f.pattern_name for f in findings]
        self.assertIn("private-key", names)

    def test_no_false_positive_on_safe_code(self):
        code = "x = 42\nprint('hello')"
        findings = self.detector.scan(code)
        self.assertEqual(len(findings), 0)


class TestSecretDetectorEntropy(unittest.TestCase):
    def test_calculate_entropy_empty(self):
        self.assertEqual(SecretDetector._calculate_entropy(""), 0.0)

    def test_calculate_entropy_uniform(self):
        # "aaaa" = 0 entropy
        self.assertAlmostEqual(SecretDetector._calculate_entropy("aaaa"), 0.0)

    def test_calculate_entropy_high(self):
        # Random-looking string should have higher entropy
        entropy = SecretDetector._calculate_entropy("aB3$xZ9!mN7@pQ2&")
        self.assertGreater(entropy, 3.0)

    def test_high_entropy_detection(self):
        # A high-entropy 20-char string
        code = 'secret = "aB3xZ9mN7pQ2kL5vR8wT"'
        detector = SecretDetector()
        findings = detector.scan(code)
        # Should catch either via pattern or entropy
        self.assertGreater(len(findings), 0)


class TestSecretDetectorCustomPattern(unittest.TestCase):
    def test_add_and_detect(self):
        detector = SecretDetector()
        detector.add_pattern("custom-token", r"CUSTOM_[A-Z]{10,}")
        code = 'tok = "CUSTOM_ABCDEFGHIJ"'
        findings = detector.scan(code)
        names = [f.pattern_name for f in findings]
        self.assertIn("custom-token", names)


class TestSecretDetectorIsIgnored(unittest.TestCase):
    def test_no_patterns(self):
        self.assertFalse(SecretDetector.is_ignored("file.py"))

    def test_matching_pattern(self):
        self.assertTrue(SecretDetector.is_ignored(".env", ["*.env", ".env"]))

    def test_non_matching(self):
        self.assertFalse(SecretDetector.is_ignored("app.py", ["*.env"]))


class TestSecretDetectorSummary(unittest.TestCase):
    def test_empty(self):
        detector = SecretDetector()
        self.assertEqual(detector.summary([]), "No secrets detected.")

    def test_with_findings(self):
        detector = SecretDetector()
        findings = [
            SecretFinding(file="f", line=1, pattern_name="aws-access-key", matched_text="x"),
            SecretFinding(file="f", line=2, pattern_name="aws-access-key", matched_text="y"),
        ]
        result = detector.summary(findings)
        self.assertIn("Secrets detected: 2", result)
        self.assertIn("aws-access-key: 2", result)


if __name__ == "__main__":
    unittest.main()
