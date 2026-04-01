"""Tests for smart_refactor.extract_engine."""
from __future__ import annotations

import unittest

from lidco.smart_refactor.extract_engine import (
    ExtractEngine,
    ExtractionResult,
    ExtractionType,
)


class TestExtractionType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ExtractionType.METHOD, "method")
        self.assertEqual(ExtractionType.VARIABLE, "variable")
        self.assertEqual(ExtractionType.CONSTANT, "constant")
        self.assertEqual(ExtractionType.CLASS, "class")


class TestExtractionResult(unittest.TestCase):
    def test_frozen(self):
        r = ExtractionResult(
            type=ExtractionType.METHOD,
            original="x",
            extracted_name="f",
            extracted_code="def f(): pass",
            remaining_code="f()",
        )
        with self.assertRaises(AttributeError):
            r.success = False  # type: ignore[misc]

    def test_defaults(self):
        r = ExtractionResult(
            type=ExtractionType.VARIABLE,
            original="",
            extracted_name="v",
            extracted_code="",
            remaining_code="",
        )
        self.assertTrue(r.success)
        self.assertEqual(r.error, "")


class TestExtractMethod(unittest.TestCase):
    def test_basic_extraction(self):
        src = "a = 1\nb = 2\nc = 3\n"
        engine = ExtractEngine()
        result = engine.extract_method(src, 2, 2, "helper")
        self.assertTrue(result.success)
        self.assertIn("def helper():", result.extracted_code)
        self.assertIn("helper()", result.remaining_code)
        self.assertNotIn("b = 2", result.remaining_code)

    def test_multi_line_extraction(self):
        src = "x = 1\ny = 2\nz = 3\nw = 4\n"
        engine = ExtractEngine()
        result = engine.extract_method(src, 2, 3, "mid")
        self.assertTrue(result.success)
        self.assertIn("y = 2", result.extracted_code)
        self.assertIn("z = 3", result.extracted_code)
        self.assertIn("mid()", result.remaining_code)

    def test_invalid_range(self):
        src = "a = 1\n"
        engine = ExtractEngine()
        result = engine.extract_method(src, 0, 5, "bad")
        self.assertFalse(result.success)
        self.assertIn("Invalid", result.error)

    def test_start_greater_than_end(self):
        src = "a = 1\nb = 2\n"
        engine = ExtractEngine()
        result = engine.extract_method(src, 2, 1, "bad")
        self.assertFalse(result.success)


class TestExtractVariable(unittest.TestCase):
    def test_basic(self):
        src = "result = compute(a + b)\n"
        engine = ExtractEngine()
        result = engine.extract_variable(src, "a + b", "total")
        self.assertTrue(result.success)
        self.assertIn("total = a + b", result.remaining_code)
        self.assertIn("total", result.remaining_code)

    def test_not_found(self):
        src = "x = 1\n"
        engine = ExtractEngine()
        result = engine.extract_variable(src, "missing_expr", "v")
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)


class TestExtractConstant(unittest.TestCase):
    def test_basic(self):
        src = 'url = "http://example.com"\nprint(url)\n'
        engine = ExtractEngine()
        result = engine.extract_constant(src, '"http://example.com"', "BASE_URL")
        self.assertTrue(result.success)
        self.assertIn("BASE_URL", result.remaining_code)

    def test_not_found(self):
        src = "x = 1\n"
        engine = ExtractEngine()
        result = engine.extract_constant(src, "999", "LIMIT")
        self.assertFalse(result.success)


class TestPreview(unittest.TestCase):
    def test_success_preview_has_diff(self):
        src = "a = 1\nb = 2\nc = 3\n"
        engine = ExtractEngine()
        result = engine.extract_method(src, 2, 2, "helper")
        preview = engine.preview(result)
        self.assertIn("---", preview)
        self.assertIn("+++", preview)

    def test_error_preview(self):
        r = ExtractionResult(
            type=ExtractionType.METHOD,
            original="",
            extracted_name="f",
            extracted_code="",
            remaining_code="",
            success=False,
            error="boom",
        )
        engine = ExtractEngine()
        self.assertIn("boom", engine.preview(r))


if __name__ == "__main__":
    unittest.main()
