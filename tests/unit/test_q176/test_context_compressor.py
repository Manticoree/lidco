"""Tests for ContextCompressor — Q176."""
from __future__ import annotations

import unittest

from lidco.input.context_compressor import ContextCompressor, CompressedResult


SAMPLE_PYTHON = '''\
import os
from pathlib import Path


class MyClass:
    """A sample class."""

    def __init__(self, name: str):
        """Initialize with name."""
        self.name = name
        self.count = 0

    def greet(self) -> str:
        """Return a greeting."""
        msg = f"Hello, {self.name}!"
        print(msg)
        return msg

    def increment(self) -> int:
        """Increment counter."""
        self.count += 1
        return self.count


def standalone_func(x: int, y: int) -> int:
    """Add two numbers."""
    result = x + y
    return result
'''

SAMPLE_SIMPLE = '''\
def foo():
    """Docstring."""
    x = 1
    y = 2
    return x + y
'''


class TestContextCompressor(unittest.TestCase):
    def setUp(self):
        self.compressor = ContextCompressor()

    # --- Basic compression ---
    def test_compress_reduces_lines(self):
        result = self.compressor.compress(SAMPLE_PYTHON)
        self.assertLess(result.compressed_lines, result.original_lines)

    def test_compress_keeps_imports(self):
        result = self.compressor.compress(SAMPLE_PYTHON)
        self.assertIn("import os", result.content)
        self.assertIn("from pathlib import Path", result.content)

    def test_compress_keeps_class_def(self):
        result = self.compressor.compress(SAMPLE_PYTHON)
        self.assertIn("class MyClass:", result.content)

    def test_compress_keeps_function_def(self):
        result = self.compressor.compress(SAMPLE_PYTHON)
        self.assertIn("def __init__", result.content)
        self.assertIn("def greet", result.content)

    def test_compress_keeps_docstrings(self):
        result = self.compressor.compress(SAMPLE_PYTHON)
        self.assertIn("A sample class", result.content)
        self.assertIn("Return a greeting", result.content)

    def test_compress_keeps_standalone_func(self):
        result = self.compressor.compress(SAMPLE_PYTHON)
        self.assertIn("def standalone_func", result.content)

    def test_compress_drops_body_lines(self):
        result = self.compressor.compress(SAMPLE_PYTHON, ratio=0.3)
        # Body lines like print(msg) should be replaced with ...
        self.assertNotIn("print(msg)", result.content)

    # --- Ratio control ---
    def test_ratio_one_keeps_everything(self):
        result = self.compressor.compress(SAMPLE_PYTHON, ratio=1.0)
        self.assertEqual(result.original_lines, result.compressed_lines)
        self.assertEqual(result.content, SAMPLE_PYTHON)

    def test_ratio_zero_minimal(self):
        result = self.compressor.compress(SAMPLE_PYTHON, ratio=0.0)
        self.assertLess(result.compressed_lines, result.original_lines)

    def test_high_ratio_keeps_more(self):
        low = self.compressor.compress(SAMPLE_PYTHON, ratio=0.2)
        high = self.compressor.compress(SAMPLE_PYTHON, ratio=0.8)
        self.assertLessEqual(low.compressed_lines, high.compressed_lines)

    # --- CompressedResult fields ---
    def test_original_lines_count(self):
        result = self.compressor.compress(SAMPLE_PYTHON)
        expected = len(SAMPLE_PYTHON.split("\n"))
        self.assertEqual(result.original_lines, expected)

    def test_ratio_is_fraction(self):
        result = self.compressor.compress(SAMPLE_PYTHON)
        self.assertGreater(result.ratio, 0.0)
        self.assertLessEqual(result.ratio, 1.0)

    def test_compressed_lines_matches_content(self):
        result = self.compressor.compress(SAMPLE_PYTHON)
        actual_lines = len(result.content.split("\n"))
        self.assertEqual(result.compressed_lines, actual_lines)

    # --- Edge cases ---
    def test_empty_string(self):
        result = self.compressor.compress("")
        self.assertEqual(result.original_lines, 0)
        self.assertEqual(result.compressed_lines, 0)
        self.assertEqual(result.content, "")

    def test_whitespace_only(self):
        result = self.compressor.compress("   \n   \n")
        self.assertEqual(result.content, "")

    def test_single_line(self):
        result = self.compressor.compress("import os")
        self.assertIn("import os", result.content)

    def test_only_imports(self):
        code = "import os\nimport sys\nfrom pathlib import Path\n"
        result = self.compressor.compress(code)
        self.assertIn("import os", result.content)
        self.assertIn("import sys", result.content)

    def test_simple_function(self):
        result = self.compressor.compress(SAMPLE_SIMPLE)
        self.assertIn("def foo():", result.content)
        self.assertIn("Docstring", result.content)

    def test_compressed_result_frozen(self):
        result = self.compressor.compress("x = 1")
        with self.assertRaises(AttributeError):
            result.content = "y = 2"  # type: ignore[misc]

    def test_decorator_kept(self):
        code = "@staticmethod\ndef foo():\n    return 1\n"
        result = self.compressor.compress(code)
        self.assertIn("@staticmethod", result.content)

    def test_async_def_kept(self):
        code = "async def bar(x):\n    await something()\n    return x\n"
        result = self.compressor.compress(code)
        self.assertIn("async def bar", result.content)


if __name__ == "__main__":
    unittest.main()
