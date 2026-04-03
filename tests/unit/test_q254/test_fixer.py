"""Tests for SmellFixer — Q254."""

from __future__ import annotations

import unittest

from lidco.smells.catalog import SmellCatalog
from lidco.smells.fixer import FixResult, SmellFixer
from lidco.smells.scanner import SmellMatch


class TestFixResult(unittest.TestCase):
    """FixResult dataclass basics."""

    def test_create(self):
        r = FixResult("magic_number", "x = 42", "CONST = 42\nx = CONST", "extracted")
        self.assertEqual(r.smell_id, "magic_number")
        self.assertEqual(r.description, "extracted")

    def test_frozen(self):
        r = FixResult("a", "b", "c", "d")
        with self.assertRaises(AttributeError):
            r.smell_id = "other"  # type: ignore[misc]


class TestFixMagicNumber(unittest.TestCase):
    """fix for magic_number smell."""

    def setUp(self):
        self.catalog = SmellCatalog.with_defaults()
        self.fixer = SmellFixer(self.catalog)

    def test_fix_magic_number(self):
        src = "timeout = 3600"
        match = SmellMatch("magic_number", "", 1, "Magic number 3600", "medium")
        result = self.fixer.fix(match, src)
        self.assertIsNotNone(result)
        self.assertEqual(result.smell_id, "magic_number")
        self.assertIn("CONST_3600", result.fixed)
        self.assertIn("3600", result.description)

    def test_fix_bad_line(self):
        src = "x = 0"
        match = SmellMatch("magic_number", "", 99, "Magic number 42", "medium")
        result = self.fixer.fix(match, src)
        self.assertIsNone(result)


class TestFixCommentedCode(unittest.TestCase):
    """fix for commented_code smell."""

    def setUp(self):
        self.catalog = SmellCatalog.with_defaults()
        self.fixer = SmellFixer(self.catalog)

    def test_fix_removes_line(self):
        src = "x = 1\n# old_code()\ny = 2"
        match = SmellMatch("commented_code", "", 2, "Commented code", "low")
        result = self.fixer.fix(match, src)
        self.assertIsNotNone(result)
        self.assertNotIn("old_code", result.fixed)
        self.assertIn("x = 1", result.fixed)
        self.assertIn("y = 2", result.fixed)

    def test_fix_bad_line(self):
        src = "x = 1"
        match = SmellMatch("commented_code", "", 99, "Commented code", "low")
        result = self.fixer.fix(match, src)
        self.assertIsNone(result)


class TestFixUnknownSmell(unittest.TestCase):
    """fix returns None for unsupported smell ids."""

    def test_no_handler(self):
        fixer = SmellFixer(SmellCatalog.with_defaults())
        match = SmellMatch("god_class", "", 1, "Too big", "critical")
        result = fixer.fix(match, "class Big: pass")
        self.assertIsNone(result)


class TestPreview(unittest.TestCase):
    """preview diff output."""

    def setUp(self):
        self.fixer = SmellFixer(SmellCatalog.with_defaults())

    def test_preview_with_fix(self):
        src = "timeout = 3600"
        match = SmellMatch("magic_number", "", 1, "Magic number 3600", "medium")
        preview = self.fixer.preview(match, src)
        # Should contain diff markers
        self.assertIsInstance(preview, str)

    def test_preview_no_fix(self):
        match = SmellMatch("god_class", "", 1, "Too big", "critical")
        preview = self.fixer.preview(match, "class Big: pass")
        self.assertIn("No automated fix", preview)


class TestBatchFix(unittest.TestCase):
    """batch_fix applies multiple fixes."""

    def setUp(self):
        self.fixer = SmellFixer(SmellCatalog.with_defaults())

    def test_batch_fix_multiple(self):
        src = "timeout = 3600\n# old\ny = 42"
        matches = [
            SmellMatch("magic_number", "", 1, "Magic 3600", "medium"),
            SmellMatch("commented_code", "", 2, "Commented code", "low"),
        ]
        results = self.fixer.batch_fix(matches, src)
        self.assertGreaterEqual(len(results), 1)
        for r in results:
            self.assertIsInstance(r, FixResult)

    def test_batch_fix_empty(self):
        results = self.fixer.batch_fix([], "x = 1")
        self.assertEqual(results, [])

    def test_batch_fix_no_handlers(self):
        matches = [SmellMatch("god_class", "", 1, "Big", "critical")]
        results = self.fixer.batch_fix(matches, "class Big: pass")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
