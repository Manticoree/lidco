"""Tests for sec_intel.dep_auditor — DepAuditor, Advisory."""
from __future__ import annotations

import unittest

from lidco.sec_intel.dep_auditor import Advisory, DepAuditor
from lidco.sec_intel.vuln_scanner import Severity


class TestAdvisory(unittest.TestCase):
    def test_frozen(self):
        a = Advisory(package="flask", version="1.0")
        with self.assertRaises(AttributeError):
            a.package = "x"  # type: ignore[misc]

    def test_defaults(self):
        a = Advisory(package="p", version="1.0")
        self.assertEqual(a.cve, "")
        self.assertEqual(a.severity, Severity.MEDIUM)
        self.assertEqual(a.description, "")
        self.assertEqual(a.fix_version, "")

    def test_equality(self):
        a = Advisory(package="p", version="1.0", cve="CVE-1")
        b = Advisory(package="p", version="1.0", cve="CVE-1")
        self.assertEqual(a, b)


class TestDepAuditorParseRequirements(unittest.TestCase):
    def setUp(self):
        self.auditor = DepAuditor()

    def test_parse_simple(self):
        text = "flask==2.0.1\nrequests==2.28.0\n"
        result = self.auditor.parse_requirements(text)
        self.assertEqual(result, [("flask", "2.0.1"), ("requests", "2.28.0")])

    def test_ignore_comments(self):
        text = "# comment\nflask==2.0.1\n"
        result = self.auditor.parse_requirements(text)
        self.assertEqual(len(result), 1)

    def test_ignore_no_version(self):
        text = "flask\nrequests>=2.0\n"
        result = self.auditor.parse_requirements(text)
        self.assertEqual(result, [])

    def test_empty(self):
        self.assertEqual(self.auditor.parse_requirements(""), [])


class TestDepAuditorAudit(unittest.TestCase):
    def setUp(self):
        self.auditor = DepAuditor()
        self.auditor.add_advisory(Advisory(
            package="flask", version="1.0", cve="CVE-2021-001",
            severity=Severity.HIGH, description="RCE", fix_version="2.0",
        ))
        self.auditor.add_advisory(Advisory(
            package="requests", version="2.20.0", cve="CVE-2022-002",
            severity=Severity.MEDIUM, description="SSRF",
        ))

    def test_finds_vulnerable(self):
        findings = self.auditor.audit([("flask", "1.0")])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].cve, "CVE-2021-001")

    def test_no_match(self):
        findings = self.auditor.audit([("flask", "2.0")])
        self.assertEqual(len(findings), 0)

    def test_case_insensitive_package(self):
        findings = self.auditor.audit([("Flask", "1.0")])
        self.assertEqual(len(findings), 1)


class TestDepAuditorHasVulnerability(unittest.TestCase):
    def test_true(self):
        auditor = DepAuditor()
        auditor.add_advisory(Advisory(package="p", version="1.0"))
        self.assertTrue(auditor.has_vulnerability("p", "1.0"))

    def test_false(self):
        auditor = DepAuditor()
        self.assertFalse(auditor.has_vulnerability("p", "1.0"))


class TestDepAuditorUpgradeRecommendations(unittest.TestCase):
    def test_with_fix(self):
        auditor = DepAuditor()
        findings = [Advisory(package="flask", version="1.0", fix_version="2.0")]
        recs = auditor.upgrade_recommendations(findings)
        self.assertEqual(len(recs), 1)
        self.assertIn("Upgrade flask", recs[0])
        self.assertIn("2.0", recs[0])

    def test_without_fix(self):
        auditor = DepAuditor()
        findings = [Advisory(package="flask", version="1.0")]
        recs = auditor.upgrade_recommendations(findings)
        self.assertEqual(len(recs), 0)


class TestDepAuditorSummary(unittest.TestCase):
    def test_empty(self):
        auditor = DepAuditor()
        self.assertEqual(auditor.summary([]), "No vulnerable dependencies found.")

    def test_with_findings(self):
        auditor = DepAuditor()
        findings = [
            Advisory(package="a", version="1", severity=Severity.HIGH),
            Advisory(package="b", version="1", severity=Severity.HIGH),
        ]
        result = auditor.summary(findings)
        self.assertIn("Vulnerable dependencies: 2", result)
        self.assertIn("HIGH: 2", result)


if __name__ == "__main__":
    unittest.main()
