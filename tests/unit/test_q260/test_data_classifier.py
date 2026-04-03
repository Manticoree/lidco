"""Tests for lidco.compliance.data_classifier."""
from __future__ import annotations

import unittest

from lidco.compliance.data_classifier import (
    ClassificationResult,
    DataClassifier,
    SensitivityLevel,
)


class TestSensitivityLevel(unittest.TestCase):
    def test_constants(self) -> None:
        self.assertEqual(SensitivityLevel.PUBLIC, "public")
        self.assertEqual(SensitivityLevel.INTERNAL, "internal")
        self.assertEqual(SensitivityLevel.CONFIDENTIAL, "confidential")
        self.assertEqual(SensitivityLevel.RESTRICTED, "restricted")


class TestClassificationResult(unittest.TestCase):
    def test_frozen(self) -> None:
        r = ClassificationResult(level="public", confidence=1.0, reasons=[], pii_found=[])
        with self.assertRaises(AttributeError):
            r.level = "restricted"  # type: ignore[misc]

    def test_fields(self) -> None:
        r = ClassificationResult(level="internal", confidence=0.8, reasons=["a"], pii_found=["email"])
        self.assertEqual(r.level, "internal")
        self.assertEqual(r.confidence, 0.8)
        self.assertEqual(r.reasons, ["a"])
        self.assertEqual(r.pii_found, ["email"])


class TestDataClassifier(unittest.TestCase):
    def setUp(self) -> None:
        self.clf = DataClassifier()

    def test_no_pii(self) -> None:
        result = self.clf.classify("Hello world")
        self.assertEqual(result.level, SensitivityLevel.PUBLIC)
        self.assertEqual(result.pii_found, [])

    def test_email_detection(self) -> None:
        result = self.clf.classify("Contact us at test@example.com")
        self.assertIn("email", result.pii_found)
        self.assertEqual(result.level, SensitivityLevel.CONFIDENTIAL)

    def test_ssn_detection(self) -> None:
        result = self.clf.classify("SSN: 123-45-6789")
        self.assertIn("ssn", result.pii_found)
        self.assertEqual(result.level, SensitivityLevel.RESTRICTED)

    def test_phone_detection(self) -> None:
        result = self.clf.classify("Call 555-123-4567")
        self.assertIn("phone", result.pii_found)

    def test_ip_detection(self) -> None:
        result = self.clf.classify("Server at 192.168.1.1")
        self.assertIn("ip_address", result.pii_found)
        self.assertEqual(result.level, SensitivityLevel.INTERNAL)

    def test_detect_pii_returns_dicts(self) -> None:
        detections = self.clf.detect_pii("email: a@b.com SSN: 111-22-3333")
        self.assertTrue(len(detections) >= 2)
        for d in detections:
            self.assertIn("type", d)
            self.assertIn("match", d)
            self.assertIn("position", d)

    def test_classify_file_env(self) -> None:
        result = self.clf.classify_file("FOO=bar", filename=".env")
        self.assertEqual(result.level, SensitivityLevel.RESTRICTED)

    def test_classify_file_no_hint(self) -> None:
        result = self.clf.classify_file("Hello", filename="readme.txt")
        self.assertEqual(result.level, SensitivityLevel.PUBLIC)

    def test_custom_patterns(self) -> None:
        clf = DataClassifier(custom_patterns={"badge": r"BADGE-\d+"})
        result = clf.classify("ID is BADGE-1234")
        self.assertIn("badge", result.pii_found)

    def test_add_pattern(self) -> None:
        self.clf.add_pattern("custom", r"CUST-\d+")
        result = self.clf.classify("Record CUST-999")
        self.assertIn("custom", result.pii_found)

    def test_summary(self) -> None:
        s = self.clf.summary()
        self.assertIn("pattern_count", s)
        self.assertGreaterEqual(s["pattern_count"], 6)
        self.assertIn("patterns", s)

    def test_multiple_pii_confidence(self) -> None:
        text = "Email a@b.com SSN 123-45-6789 phone 555-123-4567"
        result = self.clf.classify(text)
        self.assertGreater(result.confidence, 0.5)
        self.assertEqual(result.level, SensitivityLevel.RESTRICTED)


if __name__ == "__main__":
    unittest.main()
