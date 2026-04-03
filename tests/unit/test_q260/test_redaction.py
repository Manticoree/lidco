"""Tests for lidco.compliance.redaction."""
from __future__ import annotations

import unittest

from lidco.compliance.redaction import RedactionEngine, RedactionResult


class TestRedactionResult(unittest.TestCase):
    def test_frozen(self) -> None:
        r = RedactionResult(text="x", redacted_count=0, redacted_types=[])
        with self.assertRaises(AttributeError):
            r.text = "y"  # type: ignore[misc]


class TestRedactionEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RedactionEngine()

    def test_redact_email(self) -> None:
        result = self.engine.redact("Contact test@example.com please")
        self.assertIn("[REDACTED:email]", result.text)
        self.assertEqual(result.redacted_count, 1)
        self.assertIn("email", result.redacted_types)

    def test_redact_ssn(self) -> None:
        result = self.engine.redact("SSN: 123-45-6789")
        self.assertIn("[REDACTED:ssn]", result.text)

    def test_redact_no_match(self) -> None:
        result = self.engine.redact("Nothing sensitive here")
        self.assertEqual(result.text, "Nothing sensitive here")
        self.assertEqual(result.redacted_count, 0)
        self.assertEqual(result.redacted_types, [])

    def test_redact_specific_patterns(self) -> None:
        text = "Email test@x.com SSN 111-22-3333"
        result = self.engine.redact(text, patterns=["email"])
        self.assertIn("[REDACTED:email]", result.text)
        self.assertNotIn("[REDACTED:ssn]", result.text)

    def test_redact_pii(self) -> None:
        result = self.engine.redact_pii("phone 555-123-4567")
        self.assertIn("[REDACTED:phone]", result.text)

    def test_add_pattern(self) -> None:
        self.engine.add_pattern("badge", r"BADGE-\d+")
        result = self.engine.redact("ID BADGE-123")
        self.assertIn("[REDACTED:badge]", result.text)

    def test_create_mapping_and_restore(self) -> None:
        text = "Email: user@test.com"
        redacted, mapping = self.engine.create_mapping(text)
        self.assertNotIn("user@test.com", redacted)
        self.assertTrue(len(mapping) > 0)
        restored = self.engine.restore(redacted, mapping)
        self.assertIn("user@test.com", restored)

    def test_restore_manual(self) -> None:
        restored = self.engine.restore(
            "Hello [PH1] world",
            {"[PH1]": "secret"},
        )
        self.assertEqual(restored, "Hello secret world")

    def test_patterns_returns_dict(self) -> None:
        pats = self.engine.patterns()
        self.assertIsInstance(pats, dict)
        self.assertIn("email", pats)

    def test_report(self) -> None:
        text = "Email a@b.com and 111-22-3333"
        report = self.engine.report(text)
        self.assertIn("total", report)
        self.assertGreaterEqual(report["total"], 2)
        self.assertIn("types", report)
        self.assertIn("detections", report)

    def test_report_no_pii(self) -> None:
        report = self.engine.report("Clean text")
        self.assertEqual(report["total"], 0)

    def test_multiple_same_type(self) -> None:
        result = self.engine.redact("a@b.com and c@d.com")
        self.assertEqual(result.redacted_count, 2)
        self.assertEqual(result.redacted_types, ["email"])


if __name__ == "__main__":
    unittest.main()
