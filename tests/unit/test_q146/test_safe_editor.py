"""Tests for SafeEditor (Q146 task 865)."""
from __future__ import annotations

import unittest

from lidco.editing.edit_transaction import EditTransaction
from lidco.editing.safe_editor import EditResult, SafeEditor
from lidco.editing.undo_stack import UndoStack


class TestEditResult(unittest.TestCase):
    def test_success_result(self):
        r = EditResult(success=True, file_path="a.py", transaction=None, error=None)
        self.assertTrue(r.success)
        self.assertIsNone(r.error)

    def test_failure_result(self):
        r = EditResult(success=False, file_path="a.py", transaction=None, error="boom")
        self.assertFalse(r.success)
        self.assertEqual(r.error, "boom")


class TestSafeEditor(unittest.TestCase):
    def setUp(self):
        self.stack = UndoStack()
        self.editor = SafeEditor(undo_stack=self.stack)
        self.fs: dict[str, str] = {}

    def _read(self, path: str) -> str:
        if path not in self.fs:
            raise FileNotFoundError(f"No such file: {path}")
        return self.fs[path]

    def _write(self, path: str, content: str) -> None:
        self.fs[path] = content

    def _delete(self, path: str) -> None:
        if path not in self.fs:
            raise FileNotFoundError(f"No such file: {path}")
        del self.fs[path]

    def test_edit_success(self):
        self.fs["a.py"] = "old"
        r = self.editor.edit("a.py", "new", read_fn=self._read, write_fn=self._write)
        self.assertTrue(r.success)
        self.assertEqual(self.fs["a.py"], "new")

    def test_edit_pushes_to_stack(self):
        self.fs["a.py"] = "old"
        self.editor.edit("a.py", "new", read_fn=self._read, write_fn=self._write)
        self.assertTrue(self.stack.can_undo)

    def test_edit_transaction_label(self):
        self.fs["a.py"] = "old"
        r = self.editor.edit("a.py", "new", read_fn=self._read, write_fn=self._write)
        self.assertIn("a.py", r.transaction.label)

    def test_edit_read_failure(self):
        r = self.editor.edit("missing.py", "new", read_fn=self._read, write_fn=self._write)
        self.assertFalse(r.success)
        self.assertIn("No such file", r.error)

    def test_edit_write_failure(self):
        self.fs["a.py"] = "old"

        def bad_write(p, c):
            raise IOError("disk full")

        r = self.editor.edit("a.py", "new", read_fn=self._read, write_fn=bad_write)
        self.assertFalse(r.success)
        self.assertIn("disk full", r.error)

    def test_create_success(self):
        r = self.editor.create("new.py", "content", write_fn=self._write)
        self.assertTrue(r.success)
        self.assertEqual(self.fs["new.py"], "content")

    def test_create_pushes_to_stack(self):
        self.editor.create("new.py", "content", write_fn=self._write)
        self.assertTrue(self.stack.can_undo)

    def test_create_write_failure(self):
        def bad_write(p, c):
            raise IOError("fail")

        r = self.editor.create("x.py", "content", write_fn=bad_write)
        self.assertFalse(r.success)

    def test_delete_success(self):
        self.fs["a.py"] = "content"
        r = self.editor.delete("a.py", read_fn=self._read, delete_fn=self._delete)
        self.assertTrue(r.success)
        self.assertNotIn("a.py", self.fs)

    def test_delete_pushes_to_stack(self):
        self.fs["a.py"] = "content"
        self.editor.delete("a.py", read_fn=self._read, delete_fn=self._delete)
        self.assertTrue(self.stack.can_undo)

    def test_delete_read_failure(self):
        r = self.editor.delete("missing.py", read_fn=self._read, delete_fn=self._delete)
        self.assertFalse(r.success)

    def test_delete_delete_failure(self):
        self.fs["a.py"] = "content"

        def bad_del(p):
            raise IOError("fail")

        r = self.editor.delete("a.py", read_fn=self._read, delete_fn=bad_del)
        self.assertFalse(r.success)

    def test_undo_none_when_empty(self):
        self.assertIsNone(self.editor.undo())

    def test_redo_none_when_empty(self):
        self.assertIsNone(self.editor.redo())

    def test_preview_next_undo_none(self):
        self.assertIsNone(self.editor.preview_next_undo())

    def test_preview_next_undo(self):
        self.fs["a.py"] = "old"
        self.editor.edit("a.py", "new", read_fn=self._read, write_fn=self._write)
        preview = self.editor.preview_next_undo()
        self.assertIsNotNone(preview)
        self.assertIn("a.py", preview)
        self.assertIn("Undo", preview)

    def test_default_stack_created(self):
        editor = SafeEditor()
        self.assertIsNotNone(editor.undo_stack)

    def test_undo_stack_property(self):
        self.assertIs(self.editor.undo_stack, self.stack)

    def test_multiple_edits_undo(self):
        self.fs["a.py"] = "v1"
        self.editor.edit("a.py", "v2", read_fn=self._read, write_fn=self._write)
        self.fs["b.py"] = "x1"
        self.editor.edit("b.py", "x2", read_fn=self._read, write_fn=self._write)
        self.assertEqual(self.stack.state().undo_depth, 2)

    def test_edit_result_file_path(self):
        self.fs["a.py"] = "old"
        r = self.editor.edit("a.py", "new", read_fn=self._read, write_fn=self._write)
        self.assertEqual(r.file_path, "a.py")

    def test_create_result_file_path(self):
        r = self.editor.create("new.py", "c", write_fn=self._write)
        self.assertEqual(r.file_path, "new.py")


if __name__ == "__main__":
    unittest.main()
