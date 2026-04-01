"""Tests for smart_refactor.inline_engine."""
from __future__ import annotations

import unittest

from lidco.smart_refactor.inline_engine import (
    InlineEngine,
    InlineResult,
    InlineType,
)


class TestInlineType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(InlineType.VARIABLE, "variable")
        self.assertEqual(InlineType.METHOD, "method")
        self.assertEqual(InlineType.CONSTANT, "constant")


class TestInlineResult(unittest.TestCase):
    def test_frozen(self):
        r = InlineResult(type=InlineType.VARIABLE, name="x")
        with self.assertRaises(AttributeError):
            r.name = "y"  # type: ignore[misc]

    def test_defaults(self):
        r = InlineResult(type=InlineType.VARIABLE, name="v")
        self.assertEqual(r.occurrences, 0)
        self.assertEqual(r.result_code, "")
        self.assertTrue(r.success)
        self.assertEqual(r.error, "")


class TestInlineVariable(unittest.TestCase):
    def test_basic_inline(self):
        src = "tmp = a + b\nresult = tmp * 2\n"
        engine = InlineEngine()
        result = engine.inline_variable(src, "tmp")
        self.assertTrue(result.success)
        self.assertNotIn("tmp = a + b", result.result_code)
        self.assertIn("a + b", result.result_code)

    def test_not_found(self):
        src = "x = 1\n"
        engine = InlineEngine()
        result = engine.inline_variable(src, "missing")
        self.assertFalse(result.success)
        self.assertIn("No assignment", result.error)

    def test_multiple_usages(self):
        src = "val = 10\nx = val\ny = val\n"
        engine = InlineEngine()
        result = engine.inline_variable(src, "val")
        self.assertTrue(result.success)
        self.assertEqual(result.occurrences, 2)


class TestInlineConstant(unittest.TestCase):
    def test_basic(self):
        src = 'MAX = 100\nif x > MAX:\n    print(MAX)\n'
        engine = InlineEngine()
        result = engine.inline_constant(src, "MAX", "100")
        self.assertTrue(result.success)
        self.assertIn("100", result.result_code)
        self.assertNotIn("MAX = 100", result.result_code)

    def test_not_found(self):
        src = "x = 1\n"
        engine = InlineEngine()
        result = engine.inline_constant(src, "MISSING", "0")
        self.assertFalse(result.success)


class TestDetectInlinable(unittest.TestCase):
    def test_single_use_detected(self):
        src = "x = compute()\nresult = x + 1\n"
        engine = InlineEngine()
        inlinable = engine.detect_inlinable(src)
        self.assertIn("x", inlinable)

    def test_multi_use_not_detected(self):
        src = "x = 1\ny = x\nz = x\n"
        engine = InlineEngine()
        inlinable = engine.detect_inlinable(src)
        self.assertNotIn("x", inlinable)

    def test_syntax_error(self):
        engine = InlineEngine()
        self.assertEqual(engine.detect_inlinable("def (broken"), [])


class TestPreview(unittest.TestCase):
    def test_success_preview(self):
        r = InlineResult(
            type=InlineType.VARIABLE,
            name="tmp",
            occurrences=2,
            result_code="result = a + b\n",
            success=True,
        )
        engine = InlineEngine()
        text = engine.preview(r)
        self.assertIn("tmp", text)
        self.assertIn("2", text)

    def test_error_preview(self):
        r = InlineResult(
            type=InlineType.VARIABLE,
            name="x",
            success=False,
            error="not found",
        )
        engine = InlineEngine()
        self.assertIn("not found", engine.preview(r))


if __name__ == "__main__":
    unittest.main()
