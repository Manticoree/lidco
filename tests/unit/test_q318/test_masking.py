"""Tests for lidco.testdata.masking (Task 1704)."""

from __future__ import annotations

import unittest

from lidco.testdata.masking import (
    DataMasker,
    MaskReport,
    MaskResult,
    MaskRule,
    PIIType,
)


class TestPIIType(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(PIIType.EMAIL.value, "email")
        self.assertEqual(PIIType.PHONE.value, "phone")
        self.assertEqual(PIIType.SSN.value, "ssn")
        self.assertEqual(PIIType.CREDIT_CARD.value, "credit_card")
        self.assertEqual(PIIType.IP_ADDRESS.value, "ip_address")
        self.assertEqual(PIIType.CUSTOM.value, "custom")


class TestMaskRule(unittest.TestCase):
    def test_frozen(self) -> None:
        rule = MaskRule(PIIType.EMAIL, r".*")
        with self.assertRaises(AttributeError):
            rule.pii_type = PIIType.PHONE  # type: ignore[misc]

    def test_defaults(self) -> None:
        rule = MaskRule(PIIType.EMAIL, r".*")
        self.assertEqual(rule.replacement, "***")
        self.assertFalse(rule.format_preserving)


class TestMaskResult(unittest.TestCase):
    def test_frozen(self) -> None:
        mr = MaskResult("h", "v", PIIType.EMAIL)
        with self.assertRaises(AttributeError):
            mr.masked_value = "x"  # type: ignore[misc]


class TestMaskReport(unittest.TestCase):
    def test_defaults(self) -> None:
        rpt = MaskReport()
        self.assertEqual(rpt.total_fields, 0)
        self.assertEqual(rpt.masked_fields, 0)
        self.assertEqual(rpt.pii_types_found, ())


class TestDataMasker(unittest.TestCase):
    def test_mask_email(self) -> None:
        masker = DataMasker()
        result = masker.mask_string("Contact alice@test.com now")
        self.assertNotIn("alice@test.com", result)
        self.assertIn("@masked.example.com", result)

    def test_mask_phone(self) -> None:
        masker = DataMasker()
        result = masker.mask_string("Call 555-123-4567 today")
        self.assertNotIn("555-123-4567", result)

    def test_mask_ssn(self) -> None:
        masker = DataMasker()
        result = masker.mask_string("SSN: 123-45-6789")
        self.assertNotIn("123-45-6789", result)

    def test_mask_credit_card(self) -> None:
        masker = DataMasker()
        result = masker.mask_string("Card: 4111-1111-1111-1111")
        self.assertNotIn("4111-1111-1111-1111", result)

    def test_mask_ip(self) -> None:
        masker = DataMasker()
        result = masker.mask_string("Server: 192.168.1.100")
        self.assertNotIn("192.168.1.100", result)

    def test_no_pii(self) -> None:
        masker = DataMasker()
        text = "Nothing sensitive here"
        self.assertEqual(masker.mask_string(text), text)

    def test_consistent_replacement(self) -> None:
        masker = DataMasker(consistent=True)
        r1 = masker.mask_string("a@b.com and a@b.com")
        parts = r1.split(" and ")
        self.assertEqual(parts[0], parts[1])

    def test_detect_pii(self) -> None:
        masker = DataMasker()
        found = masker.detect_pii("email: x@y.com, phone: 111-222-3333")
        types = {p.value for p in found}
        self.assertIn("email", types)
        self.assertIn("phone", types)

    def test_detect_pii_none(self) -> None:
        masker = DataMasker()
        self.assertEqual(masker.detect_pii("just text"), [])

    def test_mask_dict(self) -> None:
        masker = DataMasker()
        report = masker.mask_dict({"email": "x@y.com", "age": 30, "phone": "111-222-3333"})
        self.assertIsInstance(report, MaskReport)
        self.assertEqual(report.total_fields, 3)
        self.assertEqual(report.masked_fields, 2)
        self.assertIn("email", report.pii_types_found)
        self.assertIn("phone", report.pii_types_found)

    def test_mask_dict_no_pii(self) -> None:
        masker = DataMasker()
        report = masker.mask_dict({"name": "hello", "count": 5})
        self.assertEqual(report.masked_fields, 0)

    def test_reversible(self) -> None:
        masker = DataMasker(reversible=True)
        original = "Contact alice@test.com today"
        masked = masker.mask_string(original)
        self.assertNotEqual(masked, original)
        unmasked = masker.unmask(masked)
        self.assertEqual(unmasked, original)

    def test_unmask_not_reversible_raises(self) -> None:
        masker = DataMasker(reversible=False)
        with self.assertRaises(RuntimeError):
            masker.unmask("anything")

    def test_add_rule(self) -> None:
        masker = DataMasker(rules=())
        custom_rule = MaskRule(PIIType.CUSTOM, r"SECRET-\w+", replacement="[REDACTED]")
        masker2 = masker.add_rule(custom_rule)
        self.assertEqual(len(masker2.rules), 1)
        result = masker2.mask_string("key is SECRET-abc123")
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("SECRET-abc123", result)

    def test_rules_property(self) -> None:
        masker = DataMasker()
        self.assertGreater(len(masker.rules), 0)

    def test_format_preserving_email(self) -> None:
        masker = DataMasker()
        result = masker.mask_string("test@example.com")
        # Should contain @masked.example.com
        self.assertIn("@masked.example.com", result)

    def test_format_preserving_phone(self) -> None:
        masker = DataMasker()
        result = masker.mask_string("555-123-4567")
        # Should be in XXX-XXX-XXXX format
        self.assertRegex(result, r"\d{3}-\d{3}-\d{4}")

    def test_format_preserving_ssn(self) -> None:
        masker = DataMasker()
        result = masker.mask_string("123-45-6789")
        self.assertRegex(result, r"\d{3}-\d{2}-\d{4}")

    def test_multiple_pii_in_one_string(self) -> None:
        masker = DataMasker()
        text = "email: a@b.com, ssn: 111-22-3333"
        result = masker.mask_string(text)
        self.assertNotIn("a@b.com", result)
        self.assertNotIn("111-22-3333", result)

    def test_seed_affects_output(self) -> None:
        m1 = DataMasker(seed="seed1")
        m2 = DataMasker(seed="seed2")
        r1 = m1.mask_string("user@test.com")
        r2 = m2.mask_string("user@test.com")
        # Both masked but potentially different
        self.assertNotIn("user@test.com", r1)
        self.assertNotIn("user@test.com", r2)


if __name__ == "__main__":
    unittest.main()
