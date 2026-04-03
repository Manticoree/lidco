"""Tests for lidco.compliance.reporter."""
from __future__ import annotations

import json
import unittest

from lidco.compliance.reporter import ComplianceCheck, ComplianceReporter


class TestComplianceCheck(unittest.TestCase):
    def test_frozen(self) -> None:
        c = ComplianceCheck(framework="soc2", control="x", status="pass", evidence="ok")
        with self.assertRaises(AttributeError):
            c.status = "fail"  # type: ignore[misc]

    def test_default_recommendation(self) -> None:
        c = ComplianceCheck(framework="soc2", control="x", status="pass", evidence="ok")
        self.assertEqual(c.recommendation, "")


class TestComplianceReporter(unittest.TestCase):
    def setUp(self) -> None:
        self.reporter = ComplianceReporter()

    def test_soc2_all_pass(self) -> None:
        ctx = {"access_control": True, "audit_logging": True, "encryption": True, "backup": True, "monitoring": True}
        checks = self.reporter.check_soc2(ctx)
        self.assertTrue(all(c.status == "pass" for c in checks))

    def test_soc2_all_fail(self) -> None:
        checks = self.reporter.check_soc2({})
        statuses = {c.status for c in checks}
        self.assertTrue(statuses & {"fail", "warning"})

    def test_gdpr_checks(self) -> None:
        checks = self.reporter.check_gdpr({})
        self.assertTrue(len(checks) >= 4)
        controls = {c.control for c in checks}
        self.assertIn("consent", controls)
        self.assertIn("right_to_delete", controls)

    def test_hipaa_checks(self) -> None:
        checks = self.reporter.check_hipaa({})
        self.assertTrue(len(checks) >= 3)
        controls = {c.control for c in checks}
        self.assertIn("phi_protection", controls)

    def test_run_all(self) -> None:
        result = self.reporter.run_all({})
        self.assertIn("soc2", result)
        self.assertIn("gdpr", result)
        self.assertIn("hipaa", result)

    def test_gap_analysis_returns_failures(self) -> None:
        gaps = self.reporter.gap_analysis({})
        self.assertTrue(len(gaps) > 0)
        for g in gaps:
            self.assertEqual(g.status, "fail")

    def test_gap_analysis_empty_when_compliant(self) -> None:
        ctx = {
            "access_control": True, "audit_logging": True, "encryption": True,
            "backup": True, "monitoring": True, "data_minimization": True,
            "consent": True, "right_to_delete": True, "data_portability": True,
            "breach_notification": True, "phi_protection": True, "access_audit": True,
            "baa": True,
        }
        gaps = self.reporter.gap_analysis(ctx)
        self.assertEqual(len(gaps), 0)

    def test_export_report_json(self) -> None:
        report_str = self.reporter.export_report({})
        data = json.loads(report_str)
        self.assertIn("timestamp", data)
        self.assertIn("frameworks", data)
        self.assertIn("soc2", data["frameworks"])

    def test_summary(self) -> None:
        s = self.reporter.summary({})
        self.assertIn("soc2", s)
        self.assertIn("pass", s["soc2"])
        self.assertIn("fail", s["soc2"])

    def test_hipaa_all_pass(self) -> None:
        ctx = {"phi_protection": True, "access_audit": True, "encryption": True, "baa": True}
        checks = self.reporter.check_hipaa(ctx)
        self.assertTrue(all(c.status == "pass" for c in checks))


if __name__ == "__main__":
    unittest.main()
