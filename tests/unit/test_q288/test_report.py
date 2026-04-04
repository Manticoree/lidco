"""Tests for lidco.verify.report — VerificationReport."""
from __future__ import annotations

import unittest

from lidco.verify.report import VerificationReport, ReportResult, ReportSection


class TestVerificationReport(unittest.TestCase):
    def setUp(self):
        self.report = VerificationReport()

    # -- add_section -------------------------------------------------------

    def test_add_section(self):
        self.report.add_section("logic", ["issue A"])
        result = self.report.generate()
        self.assertEqual(len(result.sections), 1)
        self.assertEqual(result.sections[0].name, "logic")

    def test_add_multiple_sections(self):
        self.report.add_section("a", [])
        self.report.add_section("b", ["x"])
        result = self.report.generate()
        self.assertEqual(len(result.sections), 2)

    # -- confidence_score --------------------------------------------------

    def test_score_no_sections_is_zero(self):
        self.assertEqual(self.report.confidence_score(), 0.0)

    def test_score_all_clean(self):
        self.report.add_section("a", [])
        self.report.add_section("b", [])
        score = self.report.confidence_score()
        self.assertEqual(score, 1.0)

    def test_score_mixed(self):
        self.report.add_section("clean", [])
        self.report.add_section("dirty", ["problem"])
        score = self.report.confidence_score()
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    # -- add_claim + unverified_claims ------------------------------------

    def test_unverified_claims_empty_when_no_claims(self):
        self.assertEqual(self.report.unverified_claims(), [])

    def test_unverified_claims_found(self):
        self.report.add_claim("data is encrypted")
        self.report.add_section("security", ["no issues"])
        result = self.report.unverified_claims()
        self.assertIn("data is encrypted", result)

    def test_verified_claim_not_in_unverified(self):
        self.report.add_claim("server runs")
        self.report.add_section("health", ["server runs correctly"])
        result = self.report.unverified_claims()
        self.assertEqual(result, [])

    # -- generate ----------------------------------------------------------

    def test_generate_returns_report_result(self):
        self.report.add_section("test", [])
        result = self.report.generate()
        self.assertIsInstance(result, ReportResult)
        self.assertIsInstance(result.score, float)
        self.assertIsInstance(result.recommendations, list)

    def test_generate_recommendations_for_findings(self):
        self.report.add_section("issues", ["bug found"])
        result = self.report.generate()
        self.assertTrue(any("Address" in r for r in result.recommendations))

    def test_generate_low_score_recommendation(self):
        self.report.add_section("bad", ["problem"])
        self.report.add_claim("unverified thing")
        result = self.report.generate()
        self.assertTrue(any("low" in r.lower() for r in result.recommendations))

    def test_report_section_frozen(self):
        s = ReportSection(name="x", findings=[])
        with self.assertRaises(AttributeError):
            s.name = "y"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
