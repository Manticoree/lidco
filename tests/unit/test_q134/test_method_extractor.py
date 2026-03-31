"""Tests for Q134 MethodExtractor."""
from __future__ import annotations

import unittest

from lidco.transform.method_extractor import ExtractResult, MethodExtractor


class TestExtractResult(unittest.TestCase):
    def test_defaults(self):
        r = ExtractResult(method_name="fn")
        self.assertEqual(r.method_name, "fn")
        self.assertEqual(r.parameters, [])
        self.assertEqual(r.body, "")
        self.assertEqual(r.new_source, "")


class TestMethodExtractor(unittest.TestCase):
    def setUp(self):
        self.ext = MethodExtractor()

    def test_extract_simple(self):
        src = "a = 1\nb = 2\nc = a + b\nprint(c)\n"
        result = self.ext.extract(src, 1, 2, "setup")
        self.assertEqual(result.method_name, "setup")
        self.assertIn("def setup", result.new_source)

    def test_extract_preserves_remaining(self):
        src = "a = 1\nb = 2\nc = a + b\nprint(c)\n"
        result = self.ext.extract(src, 1, 2, "setup")
        self.assertIn("print(c)", result.new_source)

    def test_extract_with_free_variables(self):
        src = "x = 10\ny = x + 1\nz = y * 2\n"
        result = self.ext.extract(src, 2, 3, "compute")
        self.assertIn("x", result.parameters)

    def test_extract_no_params_needed(self):
        src = "a = 1\nb = 2\n"
        result = self.ext.extract(src, 1, 2, "init")
        # Both are assignments, no external deps
        self.assertEqual(result.parameters, [])

    def test_extract_invalid_range_start_too_low(self):
        src = "a = 1\n"
        result = self.ext.extract(src, 0, 1, "fn")
        self.assertEqual(result.new_source, src)

    def test_extract_invalid_range_start_gt_end(self):
        src = "a = 1\nb = 2\n"
        result = self.ext.extract(src, 3, 1, "fn")
        self.assertEqual(result.new_source, src)

    def test_extract_start_beyond_lines(self):
        src = "a = 1\n"
        result = self.ext.extract(src, 100, 200, "fn")
        self.assertEqual(result.new_source, src)

    def test_extract_end_clamped(self):
        src = "a = 1\nb = 2\n"
        result = self.ext.extract(src, 1, 999, "fn")
        self.assertIn("def fn", result.new_source)

    def test_extract_call_inserted(self):
        src = "a = 1\nb = 2\nc = 3\n"
        result = self.ext.extract(src, 2, 2, "do_b")
        self.assertIn("do_b()", result.new_source)

    def test_detect_parameters_basic(self):
        src = "x = 10\ny = x + 1\n"
        params = self.ext.detect_parameters(src, 2, 2)
        self.assertIn("x", params)

    def test_detect_parameters_no_free(self):
        src = "a = 1\nb = 2\n"
        params = self.ext.detect_parameters(src, 1, 2)
        self.assertEqual(params, [])

    def test_detect_parameters_excludes_builtins(self):
        src = "x = 1\nprint(x)\n"
        params = self.ext.detect_parameters(src, 2, 2)
        self.assertIn("x", params)
        self.assertNotIn("print", params)

    def test_detect_parameters_syntax_error(self):
        params = self.ext.detect_parameters("def (", 1, 1)
        self.assertEqual(params, [])

    def test_detect_parameters_sorted(self):
        src = "a = 1\nb = 2\nz = b + a\n"
        params = self.ext.detect_parameters(src, 3, 3)
        self.assertEqual(params, sorted(params))

    def test_preview_basic(self):
        src = "x = 10\ny = x + 1\n"
        preview = self.ext.preview(src, 2, 2, "calc")
        self.assertIn("def calc", preview)
        self.assertIn("x", preview)

    def test_preview_invalid_range(self):
        self.assertEqual(self.ext.preview("a = 1\n", 0, 1, "fn"), "")
        self.assertEqual(self.ext.preview("a = 1\n", 3, 1, "fn"), "")
        self.assertEqual(self.ext.preview("a = 1\n", 100, 200, "fn"), "")

    def test_preview_does_not_modify_source(self):
        src = "a = 1\nb = 2\n"
        _ = self.ext.preview(src, 1, 1, "fn")
        # Source remains unchanged (preview is read-only)
        self.assertEqual(src, "a = 1\nb = 2\n")

    def test_extract_body_content(self):
        src = "x = 10\ny = x + 1\nz = y * 2\n"
        result = self.ext.extract(src, 2, 3, "compute")
        self.assertIn("y = x + 1", result.body)

    def test_extract_result_method_name(self):
        src = "a = 1\n"
        result = self.ext.extract(src, 1, 1, "my_func")
        self.assertEqual(result.method_name, "my_func")


if __name__ == "__main__":
    unittest.main()
