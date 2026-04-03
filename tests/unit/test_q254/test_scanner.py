"""Tests for SmellScanner — Q254."""

from __future__ import annotations

import unittest

from lidco.smells.catalog import SmellCatalog
from lidco.smells.scanner import SmellMatch, SmellScanner


class TestSmellMatch(unittest.TestCase):
    """SmellMatch dataclass basics."""

    def test_create(self):
        m = SmellMatch("long_method", "a.py", 10, "too long", "high")
        self.assertEqual(m.smell_id, "long_method")
        self.assertEqual(m.file, "a.py")
        self.assertEqual(m.line, 10)
        self.assertEqual(m.severity, "high")

    def test_frozen(self):
        m = SmellMatch("x", "f", 1, "msg", "low")
        with self.assertRaises(AttributeError):
            m.line = 99  # type: ignore[misc]


class TestScanForLongMethods(unittest.TestCase):
    """scan_for_long_methods detection."""

    def setUp(self):
        self.scanner = SmellScanner(SmellCatalog.with_defaults())

    def test_short_method_no_match(self):
        src = "def foo():\n" + "    pass\n" * 10
        matches = self.scanner.scan_for_long_methods(src, threshold=50)
        self.assertEqual(matches, [])

    def test_long_method_detected(self):
        src = "def foo():\n" + "    x = 1\n" * 60
        matches = self.scanner.scan_for_long_methods(src, threshold=50)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].smell_id, "long_method")
        self.assertIn("foo", matches[0].message)

    def test_multiple_methods(self):
        short = "def short():\n" + "    pass\n" * 5
        long = "def long_one():\n" + "    x = 1\n" * 60
        src = short + "\n" + long
        matches = self.scanner.scan_for_long_methods(src, threshold=50)
        self.assertEqual(len(matches), 1)
        self.assertIn("long_one", matches[0].message)

    def test_custom_threshold(self):
        src = "def foo():\n" + "    x = 1\n" * 6
        matches = self.scanner.scan_for_long_methods(src, threshold=5)
        self.assertEqual(len(matches), 1)


class TestScanForMagicNumbers(unittest.TestCase):
    """scan_for_magic_numbers detection."""

    def setUp(self):
        self.scanner = SmellScanner(SmellCatalog.with_defaults())

    def test_no_magic_numbers(self):
        src = "x = 0\ny = 1\nz = 2\n"
        matches = self.scanner.scan_for_magic_numbers(src)
        self.assertEqual(matches, [])

    def test_detects_magic_number(self):
        src = "timeout = 3600\n"
        matches = self.scanner.scan_for_magic_numbers(src)
        self.assertTrue(len(matches) >= 1)
        self.assertEqual(matches[0].smell_id, "magic_number")
        self.assertIn("3600", matches[0].message)

    def test_skips_comments(self):
        src = "# retry after 3600 seconds\nx = 0\n"
        matches = self.scanner.scan_for_magic_numbers(src)
        self.assertEqual(matches, [])

    def test_skips_imports(self):
        src = "import sys\n"
        matches = self.scanner.scan_for_magic_numbers(src)
        self.assertEqual(matches, [])


class TestScanForDeepNesting(unittest.TestCase):
    """scan_for_deep_nesting detection."""

    def setUp(self):
        self.scanner = SmellScanner(SmellCatalog.with_defaults())

    def test_shallow_code_no_match(self):
        src = "if True:\n    if True:\n        pass\n"
        matches = self.scanner.scan_for_deep_nesting(src, threshold=4)
        self.assertEqual(matches, [])

    def test_deep_nesting_detected(self):
        # 5 levels deep = 20 spaces
        src = " " * 20 + "x = 1\n"
        matches = self.scanner.scan_for_deep_nesting(src, threshold=4)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].smell_id, "deep_nesting")

    def test_custom_threshold(self):
        src = " " * 12 + "x = 1\n"  # depth 3
        matches = self.scanner.scan_for_deep_nesting(src, threshold=2)
        self.assertEqual(len(matches), 1)

    def test_blank_lines_skipped(self):
        src = "\n\n\n"
        matches = self.scanner.scan_for_deep_nesting(src)
        self.assertEqual(matches, [])


class TestScanText(unittest.TestCase):
    """scan_text — combined scanning."""

    def setUp(self):
        self.scanner = SmellScanner(SmellCatalog.with_defaults())

    def test_scan_text_combines_checks(self):
        src = "timeout = 3600\n" + " " * 24 + "deep = True\n"
        matches = self.scanner.scan_text(src, filename="test.py")
        smell_ids = {m.smell_id for m in matches}
        # Should find at least magic_number and deep_nesting
        self.assertIn("magic_number", smell_ids)
        self.assertIn("deep_nesting", smell_ids)

    def test_scan_text_stamps_filename(self):
        src = "timeout = 3600\n"
        matches = self.scanner.scan_text(src, filename="app.py")
        for m in matches:
            self.assertEqual(m.file, "app.py")

    def test_scan_text_empty_source(self):
        matches = self.scanner.scan_text("", filename="empty.py")
        self.assertEqual(matches, [])


class TestSummary(unittest.TestCase):
    """summary rendering."""

    def setUp(self):
        self.scanner = SmellScanner(SmellCatalog.with_defaults())

    def test_no_matches(self):
        result = self.scanner.summary([])
        self.assertIn("No code smells", result)

    def test_with_matches(self):
        matches = [
            SmellMatch("a", "f.py", 1, "msg", "high"),
            SmellMatch("b", "f.py", 2, "msg2", "medium"),
        ]
        result = self.scanner.summary(matches)
        self.assertIn("2 smell(s)", result)
        self.assertIn("high", result)
        self.assertIn("medium", result)


if __name__ == "__main__":
    unittest.main()
