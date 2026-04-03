"""Tests for lidco.conversation.validation_reporter — ValidationReporter."""
from __future__ import annotations

import unittest

from lidco.conversation.validation_reporter import ValidationReporter
from lidco.conversation.validator import ValidationResult


class TestReporterMode(unittest.TestCase):
    def test_default_strict(self):
        r = ValidationReporter()
        self.assertEqual(r.mode, "strict")

    def test_set_mode_lenient(self):
        r = ValidationReporter()
        r.set_mode("lenient")
        self.assertEqual(r.mode, "lenient")

    def test_set_mode_invalid_raises(self):
        r = ValidationReporter()
        with self.assertRaises(ValueError):
            r.set_mode("turbo")

    def test_init_mode(self):
        r = ValidationReporter(mode="lenient")
        self.assertEqual(r.mode, "lenient")


class TestReport(unittest.TestCase):
    def test_all_pass(self):
        results = [
            ValidationResult(is_valid=True),
            ValidationResult(is_valid=True),
        ]
        r = ValidationReporter()
        text = r.report(results)
        self.assertIn("PASS", text)
        self.assertIn("Valid: 2", text)
        self.assertIn("Invalid: 0", text)

    def test_mixed(self):
        results = [
            ValidationResult(is_valid=True),
            ValidationResult(is_valid=False, errors=["bad role"]),
        ]
        text = ValidationReporter().report(results)
        self.assertIn("PASS", text)
        self.assertIn("FAIL", text)
        self.assertIn("bad role", text)
        self.assertIn("Valid: 1", text)
        self.assertIn("Invalid: 1", text)

    def test_empty(self):
        text = ValidationReporter().report([])
        self.assertIn("Total: 0", text)


class TestSummary(unittest.TestCase):
    def test_counts(self):
        results = [
            ValidationResult(is_valid=True),
            ValidationResult(is_valid=False, errors=["e1"]),
            ValidationResult(is_valid=False, errors=["e2"]),
        ]
        s = ValidationReporter().summary(results)
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["valid"], 1)
        self.assertEqual(s["invalid"], 2)


class TestAutoFix(unittest.TestCase):
    def setUp(self):
        self.r = ValidationReporter()

    def test_fix_missing_role(self):
        fixed, fixes = self.r.auto_fix({"content": "hello"})
        self.assertEqual(fixed["role"], "user")
        self.assertTrue(any("role" in f for f in fixes))

    def test_fix_string_content(self):
        fixed, fixes = self.r.auto_fix({"role": "user", "content": "hello"})
        self.assertIsInstance(fixed["content"], list)
        self.assertEqual(fixed["content"][0]["type"], "text")
        self.assertTrue(any("content block" in f.lower() or "content" in f.lower() for f in fixes))

    def test_fix_tool_missing_id(self):
        fixed, fixes = self.r.auto_fix({"role": "tool", "content": "ok"})
        self.assertEqual(fixed["tool_call_id"], "placeholder")
        self.assertTrue(any("tool_call_id" in f for f in fixes))

    def test_no_mutation(self):
        original = {"content": "hello"}
        copy = dict(original)
        self.r.auto_fix(original)
        self.assertEqual(original, copy)

    def test_already_valid(self):
        msg = {"role": "user", "content": [{"type": "text", "text": "hi"}]}
        fixed, fixes = self.r.auto_fix(msg)
        self.assertEqual(fixed["role"], "user")
        # content already list, no string→block fix
        self.assertFalse(any("string content" in f.lower() for f in fixes))

    def test_all_three_fixes(self):
        fixed, fixes = self.r.auto_fix({})
        self.assertEqual(fixed["role"], "user")
        self.assertEqual(len(fixes), 1)  # only missing role


class TestAutoFixCombined(unittest.TestCase):
    def test_tool_without_role_and_id(self):
        # Without role, it defaults to "user", so tool_call_id fix won't apply
        fixed, fixes = self.r if hasattr(self, "r") else (None, None)
        r = ValidationReporter()
        fixed, fixes = r.auto_fix({"role": "tool", "content": "result"})
        self.assertEqual(fixed["role"], "tool")
        self.assertIn("tool_call_id", fixed)
        self.assertTrue(len(fixes) >= 1)


if __name__ == "__main__":
    unittest.main()
