"""Tests for Q134 VariableRenamer."""
from __future__ import annotations

import unittest

from lidco.transform.variable_renamer import RenameResult, VariableRenamer


class TestRenameResult(unittest.TestCase):
    def test_dataclass_fields(self):
        r = RenameResult(old_name="x", new_name="y", occurrences=2, source="y = 1")
        self.assertEqual(r.old_name, "x")
        self.assertEqual(r.new_name, "y")
        self.assertEqual(r.occurrences, 2)
        self.assertEqual(r.source, "y = 1")


class TestVariableRenamer(unittest.TestCase):
    def setUp(self):
        self.renamer = VariableRenamer()

    def test_rename_simple_variable(self):
        src = "x = 1\nprint(x)\n"
        result = self.renamer.rename(src, "x", "y")
        self.assertIn("y = 1", result.source)
        self.assertIn("print(y)", result.source)
        self.assertGreaterEqual(result.occurrences, 2)

    def test_rename_no_match(self):
        src = "a = 1\n"
        result = self.renamer.rename(src, "z", "w")
        self.assertEqual(result.occurrences, 0)
        self.assertEqual(result.source, src)

    def test_rename_function_param(self):
        src = "def foo(x):\n    return x + 1\n"
        result = self.renamer.rename(src, "x", "val")
        self.assertIn("val", result.source)
        self.assertNotIn("(x)", result.source)

    def test_rename_multiple_occurrences(self):
        src = "a = 1\nb = a + 2\nc = a * 3\n"
        result = self.renamer.rename(src, "a", "num")
        self.assertEqual(result.source.count("num"), result.occurrences)

    def test_rename_preserves_other_names(self):
        src = "x = 1\ny = 2\nprint(x, y)\n"
        result = self.renamer.rename(src, "x", "z")
        self.assertIn("y = 2", result.source)

    def test_rename_syntax_error(self):
        src = "def ("
        result = self.renamer.rename(src, "x", "y")
        self.assertEqual(result.occurrences, 0)
        self.assertEqual(result.source, src)

    def test_rename_empty_source(self):
        result = self.renamer.rename("", "x", "y")
        self.assertEqual(result.occurrences, 0)

    def test_find_occurrences_basic(self):
        src = "x = 1\nprint(x)\n"
        occ = self.renamer.find_occurrences(src, "x")
        self.assertGreaterEqual(len(occ), 2)

    def test_find_occurrences_no_match(self):
        src = "a = 1\n"
        occ = self.renamer.find_occurrences(src, "zzz")
        self.assertEqual(occ, [])

    def test_find_occurrences_syntax_error(self):
        occ = self.renamer.find_occurrences("def (", "x")
        self.assertEqual(occ, [])

    def test_find_occurrences_returns_sorted(self):
        src = "x = 1\ny = x\nz = x + y\n"
        occ = self.renamer.find_occurrences(src, "x")
        lines = [o[0] for o in occ]
        self.assertEqual(lines, sorted(lines))

    def test_find_occurrences_includes_args(self):
        src = "def foo(x):\n    return x\n"
        occ = self.renamer.find_occurrences(src, "x")
        self.assertGreaterEqual(len(occ), 2)

    def test_is_safe_rename_true(self):
        src = "x = 1\nprint(x)\n"
        self.assertTrue(self.renamer.is_safe_rename(src, "x", "new_var"))

    def test_is_safe_rename_conflict(self):
        src = "x = 1\ny = 2\n"
        self.assertFalse(self.renamer.is_safe_rename(src, "x", "y"))

    def test_is_safe_rename_same_name(self):
        src = "x = 1\n"
        self.assertFalse(self.renamer.is_safe_rename(src, "x", "x"))

    def test_is_safe_rename_invalid_identifier(self):
        src = "x = 1\n"
        self.assertFalse(self.renamer.is_safe_rename(src, "x", "123bad"))

    def test_is_safe_rename_old_not_found(self):
        src = "a = 1\n"
        self.assertFalse(self.renamer.is_safe_rename(src, "zzz", "www"))

    def test_is_safe_rename_syntax_error(self):
        self.assertFalse(self.renamer.is_safe_rename("def (", "x", "y"))

    def test_rename_in_class(self):
        src = "class C:\n    x = 1\n    def m(self):\n        return self.x\n"
        result = self.renamer.rename(src, "C", "D")
        self.assertIn("D", result.source)

    def test_rename_result_old_new(self):
        result = self.renamer.rename("x = 1\n", "x", "y")
        self.assertEqual(result.old_name, "x")
        self.assertEqual(result.new_name, "y")


if __name__ == "__main__":
    unittest.main()
