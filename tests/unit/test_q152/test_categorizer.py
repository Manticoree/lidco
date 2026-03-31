"""Tests for Q152 ErrorCategorizer."""
from __future__ import annotations

import unittest

from lidco.errors.categorizer import ErrorCategorizer, ErrorCategory, CategorizedError


class TestErrorCategory(unittest.TestCase):
    def test_fields(self):
        c = ErrorCategory(name="IO", pattern=r"IO", description="IO error", severity="high")
        self.assertEqual(c.name, "IO")
        self.assertEqual(c.severity, "high")

    def test_equality(self):
        a = ErrorCategory("X", "x", "desc", "low")
        b = ErrorCategory("X", "x", "desc", "low")
        self.assertEqual(a, b)


class TestCategorizedError(unittest.TestCase):
    def test_fields(self):
        err = ValueError("bad")
        ce = CategorizedError(original=err, category=None, message="bad", timestamp=1.0)
        self.assertIs(ce.original, err)
        self.assertIsNone(ce.category)
        self.assertEqual(ce.message, "bad")

    def test_with_category(self):
        cat = ErrorCategory("V", "val", "val error", "medium")
        ce = CategorizedError(original=ValueError(), category=cat, message="", timestamp=0.0)
        self.assertEqual(ce.category.name, "V")


class TestErrorCategorizer(unittest.TestCase):
    def setUp(self):
        self.cat = ErrorCategorizer()

    def test_empty_categories(self):
        self.assertEqual(self.cat.categories, [])

    def test_add_category(self):
        self.cat.add_category("IO", r"IOError", "io", "low")
        self.assertEqual(len(self.cat.categories), 1)
        self.assertEqual(self.cat.categories[0].name, "IO")

    def test_categories_returns_copy(self):
        self.cat.add_category("X", "x", "x", "low")
        cats = self.cat.categories
        cats.clear()
        self.assertEqual(len(self.cat.categories), 1)

    def test_categorize_no_match(self):
        self.cat.add_category("IO", r"IOError", "io", "low")
        ce = self.cat.categorize(ValueError("oops"))
        self.assertIsNone(ce.category)
        self.assertEqual(ce.message, "oops")

    def test_categorize_match(self):
        self.cat.add_category("Val", r"ValueError", "val", "medium")
        ce = self.cat.categorize(ValueError("bad input"))
        self.assertIsNotNone(ce.category)
        self.assertEqual(ce.category.name, "Val")

    def test_categorize_first_match_wins(self):
        self.cat.add_category("A", r"Error", "a", "low")
        self.cat.add_category("B", r"Error", "b", "high")
        ce = self.cat.categorize(RuntimeError("x"))
        self.assertEqual(ce.category.name, "A")

    def test_categorize_case_insensitive(self):
        self.cat.add_category("CI", r"notfound", "ci", "low")
        ce = self.cat.categorize(FileNotFoundError("NotFound here"))
        self.assertIsNotNone(ce.category)

    def test_categorize_timestamp(self):
        ce = self.cat.categorize(RuntimeError("x"))
        self.assertGreater(ce.timestamp, 0)

    def test_categorize_original_preserved(self):
        err = TypeError("t")
        ce = self.cat.categorize(err)
        self.assertIs(ce.original, err)

    def test_categorize_message_from_exception(self):
        ce = self.cat.categorize(RuntimeError("hello world"))
        self.assertEqual(ce.message, "hello world")

    def test_categorize_regex_pattern(self):
        self.cat.add_category("Num", r"\d+ is invalid", "num", "low")
        ce = self.cat.categorize(ValueError("42 is invalid"))
        self.assertIsNotNone(ce.category)

    def test_categorize_no_false_positive(self):
        self.cat.add_category("Specific", r"^ValueError: exact$", "s", "low")
        ce = self.cat.categorize(ValueError("not exact"))
        self.assertIsNone(ce.category)


class TestWithDefaults(unittest.TestCase):
    def setUp(self):
        self.cat = ErrorCategorizer.with_defaults()

    def test_has_categories(self):
        self.assertGreaterEqual(len(self.cat.categories), 7)

    def test_file_not_found(self):
        ce = self.cat.categorize(FileNotFoundError("missing.txt"))
        self.assertIsNotNone(ce.category)
        self.assertEqual(ce.category.name, "FileNotFound")

    def test_permission_error(self):
        ce = self.cat.categorize(PermissionError("Access denied"))
        self.assertIsNotNone(ce.category)
        self.assertEqual(ce.category.name, "PermissionError")

    def test_import_error(self):
        ce = self.cat.categorize(ImportError("No module named foo"))
        self.assertIsNotNone(ce.category)
        self.assertEqual(ce.category.name, "ImportError")

    def test_value_error(self):
        ce = self.cat.categorize(ValueError("invalid"))
        self.assertIsNotNone(ce.category)

    def test_connection_error(self):
        ce = self.cat.categorize(ConnectionError("refused"))
        self.assertIsNotNone(ce.category)
        self.assertEqual(ce.category.severity, "critical")

    def test_timeout_error(self):
        ce = self.cat.categorize(TimeoutError("timed out"))
        self.assertIsNotNone(ce.category)
        self.assertEqual(ce.category.severity, "critical")

    def test_unmatched_error(self):
        ce = self.cat.categorize(StopIteration())
        self.assertIsNone(ce.category)


if __name__ == "__main__":
    unittest.main()
