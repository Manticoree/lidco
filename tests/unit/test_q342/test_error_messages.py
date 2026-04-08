"""Tests for ErrorMessageStandardizer (Q342, Task 2)."""
from __future__ import annotations

import unittest

from lidco.stability.error_messages import ErrorMessageStandardizer


class TestAuditMessages(unittest.TestCase):
    def setUp(self):
        self.std = ErrorMessageStandardizer()

    def test_lowercase_start_flagged(self):
        src = 'raise ValueError("something went wrong")\n'
        results = self.std.audit_messages(src)
        self.assertEqual(len(results), 1)
        self.assertIn("starts_lowercase", results[0]["issues"])

    def test_no_period_flagged(self):
        src = 'raise ValueError("Something went wrong")\n'
        results = self.std.audit_messages(src)
        self.assertIn("no_period", results[0]["issues"])

    def test_correct_message_no_issues(self):
        src = 'raise ValueError("Something went wrong.")\n'
        results = self.std.audit_messages(src)
        self.assertEqual(results[0]["issues"], [])

    def test_stacktrace_in_message_flagged(self):
        src = 'raise ValueError("Traceback (most recent call last)")\n'
        results = self.std.audit_messages(src)
        self.assertIn("contains_stacktrace", results[0]["issues"])

    def test_no_raise_returns_empty(self):
        src = "x = 1\n"
        results = self.std.audit_messages(src)
        self.assertEqual(results, [])

    def test_line_number_correct(self):
        src = """\
x = 1
raise KeyError("Missing key.")
"""
        results = self.std.audit_messages(src)
        self.assertEqual(results[0]["line"], 2)


class TestCheckI18nReadiness(unittest.TestCase):
    def setUp(self):
        self.std = ErrorMessageStandardizer()

    def test_plain_string_not_ready(self):
        src = 'raise ValueError("Not found.")\n'
        results = self.std.check_i18n_readiness(src)
        self.assertFalse(results[0]["i18n_ready"])

    def test_fstring_considered_ready(self):
        src = 'raise ValueError(f"Not found: {name}.")\n'
        results = self.std.check_i18n_readiness(src)
        self.assertTrue(results[0]["i18n_ready"])

    def test_suggestion_present_when_not_ready(self):
        src = 'raise ValueError("Not found.")\n'
        results = self.std.check_i18n_readiness(src)
        self.assertIn("i18n", results[0]["suggestion"].lower())

    def test_no_raise_returns_empty(self):
        results = self.std.check_i18n_readiness("x = 1\n")
        self.assertEqual(results, [])


class TestGenerateTemplates(unittest.TestCase):
    def setUp(self):
        self.std = ErrorMessageStandardizer()

    def test_returns_dict(self):
        result = self.std.generate_templates(["Could not connect to database."])
        self.assertIsInstance(result, dict)

    def test_keys_are_err_codes(self):
        result = self.std.generate_templates(["Failed to open file '/tmp/x.txt'."])
        key = list(result.keys())[0]
        self.assertTrue(key.startswith("ERR"))

    def test_numbers_replaced_in_template(self):
        result = self.std.generate_templates(["Timeout after 30 seconds."])
        template = list(result.values())[0]
        self.assertNotIn("30", template)

    def test_multiple_messages_unique_codes(self):
        result = self.std.generate_templates(["Error A.", "Error B."])
        self.assertEqual(len(result), 2)
        keys = list(result.keys())
        self.assertNotEqual(keys[0], keys[1])

    def test_empty_list_returns_empty_dict(self):
        result = self.std.generate_templates([])
        self.assertEqual(result, {})


class TestAssignErrorCodes(unittest.TestCase):
    def setUp(self):
        self.std = ErrorMessageStandardizer()

    def test_raises_get_codes(self):
        src = 'raise ValueError("Bad value.")\n'
        results = self.std.assign_error_codes(src)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["suggested_code"].startswith("ERR"))

    def test_exception_type_captured(self):
        src = 'raise KeyError("Missing.")\n'
        results = self.std.assign_error_codes(src)
        self.assertIn("KeyError", results[0]["exception_type"])

    def test_message_captured(self):
        src = 'raise ValueError("Bad value.")\n'
        results = self.std.assign_error_codes(src)
        self.assertEqual(results[0]["message"], "Bad value.")

    def test_multiple_raises_unique_codes(self):
        src = 'raise ValueError("A.")\nraise KeyError("B.")\n'
        results = self.std.assign_error_codes(src)
        self.assertEqual(len(results), 2)
        codes = [r["suggested_code"] for r in results]
        self.assertNotEqual(codes[0], codes[1])

    def test_no_raise_returns_empty(self):
        results = self.std.assign_error_codes("x = 1\n")
        self.assertEqual(results, [])
