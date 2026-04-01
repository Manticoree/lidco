"""Tests for smart_refactor.rename_propagator."""
from __future__ import annotations

import unittest

from lidco.smart_refactor.rename_propagator import (
    RenameMatch,
    RenamePropagator,
    RenameResult,
)


class TestRenameMatch(unittest.TestCase):
    def test_frozen(self):
        m = RenameMatch(file="a.py", line=1)
        with self.assertRaises(AttributeError):
            m.file = "b.py"  # type: ignore[misc]

    def test_defaults(self):
        m = RenameMatch(file="x.py", line=5)
        self.assertEqual(m.column, 0)
        self.assertEqual(m.context, "")


class TestRenameResult(unittest.TestCase):
    def test_defaults(self):
        r = RenameResult(old_name="a", new_name="b")
        self.assertEqual(r.matches, ())
        self.assertEqual(r.files_affected, 0)
        self.assertTrue(r.success)


class TestFindReferences(unittest.TestCase):
    def test_finds_all_occurrences(self):
        src = "foo = 1\nbar = foo + foo\n"
        p = RenamePropagator()
        refs = p.find_references(src, "foo", file="test.py")
        self.assertEqual(len(refs), 3)
        self.assertTrue(all(r.file == "test.py" for r in refs))

    def test_whole_word_only(self):
        src = "foobar = 1\nfoo = 2\n"
        p = RenamePropagator()
        refs = p.find_references(src, "foo")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].line, 2)

    def test_no_matches(self):
        src = "x = 1\n"
        p = RenamePropagator()
        self.assertEqual(p.find_references(src, "missing"), [])


class TestRename(unittest.TestCase):
    def test_basic_rename(self):
        src = "old_name = 1\nprint(old_name)\n"
        p = RenamePropagator()
        result = p.rename(src, "old_name", "new_name")
        self.assertIn("new_name", result)
        self.assertNotIn("old_name", result)

    def test_preserves_substrings(self):
        src = "old_name_extra = 1\nold_name = 2\n"
        p = RenamePropagator()
        result = p.rename(src, "old_name", "new_name")
        self.assertIn("old_name_extra", result)
        self.assertIn("new_name = 2", result)


class TestRenameInFiles(unittest.TestCase):
    def test_multiple_files(self):
        sources = {
            "a.py": "foo = 1\n",
            "b.py": "from a import foo\nprint(foo)\n",
            "c.py": "x = 1\n",
        }
        p = RenamePropagator()
        result = p.rename_in_files(sources, "foo", "bar")
        self.assertEqual(result.files_affected, 2)
        self.assertGreater(len(result.matches), 0)
        self.assertTrue(result.success)

    def test_no_files_affected(self):
        sources = {"a.py": "x = 1\n"}
        p = RenamePropagator()
        result = p.rename_in_files(sources, "missing", "new")
        self.assertEqual(result.files_affected, 0)


class TestPreview(unittest.TestCase):
    def test_preview_shows_diff(self):
        sources = {"a.py": "old = 1\nprint(old)\n"}
        p = RenamePropagator()
        diff = p.preview(sources, "old", "new")
        self.assertIn("---", diff)
        self.assertIn("+++", diff)

    def test_preview_empty_when_no_changes(self):
        sources = {"a.py": "x = 1\n"}
        p = RenamePropagator()
        diff = p.preview(sources, "missing", "new")
        self.assertEqual(diff.strip(), "")


if __name__ == "__main__":
    unittest.main()
