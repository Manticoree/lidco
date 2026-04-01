"""Tests for sec_intel.vuln_scanner — VulnScanner, VulnFinding, Severity."""
from __future__ import annotations

import unittest

from lidco.sec_intel.vuln_scanner import Severity, VulnFinding, VulnScanner


class TestSeverityEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Severity.CRITICAL, "CRITICAL")
        self.assertEqual(Severity.HIGH, "HIGH")
        self.assertEqual(Severity.MEDIUM, "MEDIUM")
        self.assertEqual(Severity.LOW, "LOW")
        self.assertEqual(Severity.INFO, "INFO")

    def test_is_str(self):
        self.assertIsInstance(Severity.HIGH, str)


class TestVulnFinding(unittest.TestCase):
    def test_frozen(self):
        f = VulnFinding(rule="sql", file="a.py")
        with self.assertRaises(AttributeError):
            f.rule = "x"  # type: ignore[misc]

    def test_defaults(self):
        f = VulnFinding(rule="r", file="f")
        self.assertEqual(f.line, 0)
        self.assertEqual(f.severity, Severity.MEDIUM)
        self.assertEqual(f.description, "")
        self.assertEqual(f.fix_suggestion, "")
        self.assertEqual(f.cwe, "")

    def test_equality(self):
        a = VulnFinding(rule="r", file="f", line=1)
        b = VulnFinding(rule="r", file="f", line=1)
        self.assertEqual(a, b)


class TestVulnScannerSQLInjection(unittest.TestCase):
    def setUp(self):
        self.scanner = VulnScanner()

    def test_detects_fstring_execute(self):
        code = 'cursor.execute(f"SELECT * FROM t WHERE id={uid}")'
        findings = self.scanner.scan(code, "app.py")
        rules = [f.rule for f in findings]
        self.assertIn("sql-injection", rules)

    def test_detects_format_execute(self):
        code = 'cursor.execute("SELECT * FROM t WHERE id={}".format(uid))'
        findings = self.scanner.scan(code, "app.py")
        rules = [f.rule for f in findings]
        self.assertIn("sql-injection", rules)

    def test_safe_parameterized(self):
        code = 'cursor.execute("SELECT * FROM t WHERE id=?", (uid,))'
        findings = self.scanner.scan(code, "app.py")
        rules = [f.rule for f in findings]
        self.assertNotIn("sql-injection", rules)


class TestVulnScannerXSS(unittest.TestCase):
    def setUp(self):
        self.scanner = VulnScanner()

    def test_detects_innerhtml(self):
        code = "el.innerHTML = userInput"
        findings = self.scanner.scan(code)
        rules = [f.rule for f in findings]
        self.assertIn("xss", rules)

    def test_detects_eval(self):
        code = "eval(userInput)"
        findings = self.scanner.scan(code)
        rules = [f.rule for f in findings]
        self.assertIn("xss", rules)


class TestVulnScannerPathTraversal(unittest.TestCase):
    def setUp(self):
        self.scanner = VulnScanner()

    def test_detects_dot_dot(self):
        code = 'path = "../../etc/passwd"'
        findings = self.scanner.scan(code)
        rules = [f.rule for f in findings]
        self.assertIn("path-traversal", rules)

    def test_detects_open_fstring(self):
        code = 'open(f"/data/{user_path}")'
        findings = self.scanner.scan(code)
        rules = [f.rule for f in findings]
        self.assertIn("path-traversal", rules)


class TestVulnScannerHardcodedSecrets(unittest.TestCase):
    def setUp(self):
        self.scanner = VulnScanner()

    def test_detects_password(self):
        code = 'password = "supersecret123"'
        findings = self.scanner.scan(code)
        rules = [f.rule for f in findings]
        self.assertIn("hardcoded-secret", rules)

    def test_detects_api_key(self):
        code = 'api_key = "sk-proj-abc123xyz"'
        findings = self.scanner.scan(code)
        rules = [f.rule for f in findings]
        self.assertIn("hardcoded-secret", rules)


class TestVulnScannerCustomRule(unittest.TestCase):
    def test_add_and_detect(self):
        scanner = VulnScanner()
        scanner.add_rule("debug-mode", r"DEBUG\s*=\s*True", Severity.LOW, "Debug mode enabled")
        findings = scanner.scan("DEBUG = True", "settings.py")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "debug-mode")
        self.assertEqual(findings[0].severity, Severity.LOW)


class TestVulnScannerSummary(unittest.TestCase):
    def test_empty(self):
        scanner = VulnScanner()
        self.assertEqual(scanner.summary([]), "No vulnerabilities found.")

    def test_with_findings(self):
        scanner = VulnScanner()
        findings = [
            VulnFinding(rule="a", file="f", severity=Severity.CRITICAL),
            VulnFinding(rule="b", file="f", severity=Severity.HIGH),
            VulnFinding(rule="c", file="f", severity=Severity.CRITICAL),
        ]
        result = scanner.summary(findings)
        self.assertIn("Total findings: 3", result)
        self.assertIn("CRITICAL: 2", result)
        self.assertIn("HIGH: 1", result)


if __name__ == "__main__":
    unittest.main()
