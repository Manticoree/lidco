"""Tests for FileActionsProvider."""
from __future__ import annotations

import unittest

from lidco.actions.file_provider import FileAction, FileActionResult, FileActionsProvider


class TestFileAction(unittest.TestCase):
    def test_defaults(self):
        a = FileAction(action="create", source="f.py")
        self.assertEqual(a.target, "")
        self.assertEqual(a.template, "")

    def test_frozen(self):
        a = FileAction(action="create", source="f.py")
        with self.assertRaises(AttributeError):
            a.action = "delete"  # type: ignore[misc]


class TestFileActionsProvider(unittest.TestCase):
    def setUp(self):
        self.prov = FileActionsProvider()

    def test_create(self):
        r = self.prov.create("app.py")
        self.assertTrue(r.success)
        self.assertEqual(r.action, "create")
        self.assertIn("app.py", r.message)

    def test_create_with_template(self):
        r = self.prov.create("app.py", template="flask")
        self.assertIn("flask", r.message)

    def test_rename(self):
        r = self.prov.rename("old.py", "new.py")
        self.assertTrue(r.success)
        self.assertEqual(r.source, "old.py")
        self.assertEqual(r.target, "new.py")

    def test_move(self):
        r = self.prov.move("src/a.py", "lib/a.py")
        self.assertTrue(r.success)
        self.assertIn("Moved", r.message)

    def test_delete(self):
        r = self.prov.delete("tmp.py")
        self.assertTrue(r.success)
        self.assertIn("Deleted", r.message)

    def test_copy(self):
        r = self.prov.copy("a.py", "b.py")
        self.assertTrue(r.success)
        self.assertIn("Copied", r.message)

    def test_copy_path(self):
        self.assertEqual(self.prov.copy_path("/some/path"), "/some/path")

    def test_history(self):
        self.prov.create("a.py")
        self.prov.delete("b.py")
        hist = self.prov.history()
        self.assertEqual(len(hist), 2)

    def test_undo_last_empty(self):
        self.assertIsNone(self.prov.undo_last())

    def test_undo_last_create(self):
        self.prov.create("a.py")
        undo = self.prov.undo_last()
        self.assertIsNotNone(undo)
        self.assertEqual(undo.action, "delete")

    def test_undo_last_rename(self):
        self.prov.rename("old.py", "new.py")
        undo = self.prov.undo_last()
        self.assertEqual(undo.source, "new.py")
        self.assertEqual(undo.target, "old.py")

    def test_summary(self):
        self.prov.create("x.py")
        s = self.prov.summary()
        self.assertEqual(s["total_actions"], 1)
        self.assertIn("create", s["action_types"])


if __name__ == "__main__":
    unittest.main()
