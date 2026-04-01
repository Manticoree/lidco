"""Tests for editing.multi_edit_engine — MultiEditEngine, EditOp, EditConflict, EditResult."""
from __future__ import annotations

import unittest

from lidco.editing.multi_edit_engine import (
    EditConflict,
    EditOp,
    EditResult,
    MultiEditEngine,
)


class TestEditOp(unittest.TestCase):
    def test_frozen(self):
        op = EditOp(old_text="a", new_text="b")
        with self.assertRaises(AttributeError):
            op.old_text = "c"  # type: ignore[misc]

    def test_fields(self):
        op = EditOp(old_text="hello", new_text="world")
        self.assertEqual(op.old_text, "hello")
        self.assertEqual(op.new_text, "world")

    def test_equality(self):
        a = EditOp("x", "y")
        b = EditOp("x", "y")
        self.assertEqual(a, b)


class TestEditConflict(unittest.TestCase):
    def test_frozen(self):
        c = EditConflict(index=0, message="not found")
        with self.assertRaises(AttributeError):
            c.message = "changed"  # type: ignore[misc]

    def test_fields(self):
        c = EditConflict(index=2, message="ambiguous")
        self.assertEqual(c.index, 2)
        self.assertEqual(c.message, "ambiguous")


class TestEditResult(unittest.TestCase):
    def test_frozen(self):
        r = EditResult(success=True, content="ok", edits_applied=1, conflicts=())
        with self.assertRaises(AttributeError):
            r.success = False  # type: ignore[misc]

    def test_fields(self):
        r = EditResult(success=False, content="x", edits_applied=0, conflicts=(EditConflict(0, "err"),))
        self.assertFalse(r.success)
        self.assertEqual(r.edits_applied, 0)
        self.assertEqual(len(r.conflicts), 1)


class TestMultiEditEngineInit(unittest.TestCase):
    def test_properties(self):
        engine = MultiEditEngine("foo.py", "content")
        self.assertEqual(engine.file_path, "foo.py")
        self.assertEqual(engine.content, "content")
        self.assertEqual(engine.edits, ())


class TestMultiEditEngineAddEdit(unittest.TestCase):
    def test_returns_new_instance(self):
        e1 = MultiEditEngine("f.py", "abc")
        e2 = e1.add_edit("a", "x")
        self.assertIsNot(e1, e2)
        self.assertEqual(len(e1.edits), 0)
        self.assertEqual(len(e2.edits), 1)

    def test_chained_adds(self):
        engine = MultiEditEngine("f.py", "abc").add_edit("a", "x").add_edit("b", "y")
        self.assertEqual(len(engine.edits), 2)
        self.assertEqual(engine.edits[0].old_text, "a")
        self.assertEqual(engine.edits[1].old_text, "b")


class TestMultiEditEngineValidate(unittest.TestCase):
    def test_no_conflicts(self):
        engine = MultiEditEngine("f.py", "hello world").add_edit("hello", "hi")
        conflicts = engine.validate()
        self.assertEqual(conflicts, ())

    def test_not_found_conflict(self):
        engine = MultiEditEngine("f.py", "hello").add_edit("missing", "x")
        conflicts = engine.validate()
        self.assertEqual(len(conflicts), 1)
        self.assertIn("not found", conflicts[0].message)

    def test_ambiguous_conflict(self):
        engine = MultiEditEngine("f.py", "aaa").add_edit("a", "b")
        conflicts = engine.validate()
        self.assertEqual(len(conflicts), 1)
        self.assertIn("ambiguous", conflicts[0].message)

    def test_sequential_validation(self):
        # After first edit replaces "hello", second edit should find "hi"
        engine = (
            MultiEditEngine("f.py", "hello world")
            .add_edit("hello", "hi")
            .add_edit("hi", "hey")
        )
        conflicts = engine.validate()
        self.assertEqual(conflicts, ())


class TestMultiEditEngineApply(unittest.TestCase):
    def test_single_edit(self):
        engine = MultiEditEngine("f.py", "hello world").add_edit("hello", "hi")
        result = engine.apply()
        self.assertTrue(result.success)
        self.assertEqual(result.content, "hi world")
        self.assertEqual(result.edits_applied, 1)
        self.assertEqual(result.conflicts, ())

    def test_multiple_edits(self):
        engine = (
            MultiEditEngine("f.py", "foo bar baz")
            .add_edit("foo", "one")
            .add_edit("bar", "two")
        )
        result = engine.apply()
        self.assertTrue(result.success)
        self.assertEqual(result.content, "one two baz")
        self.assertEqual(result.edits_applied, 2)

    def test_apply_with_conflict_returns_failure(self):
        engine = MultiEditEngine("f.py", "hello").add_edit("missing", "x")
        result = engine.apply()
        self.assertFalse(result.success)
        self.assertEqual(result.edits_applied, 0)
        self.assertEqual(len(result.conflicts), 1)

    def test_no_edits(self):
        engine = MultiEditEngine("f.py", "content")
        result = engine.apply()
        self.assertTrue(result.success)
        self.assertEqual(result.content, "content")
        self.assertEqual(result.edits_applied, 0)


class TestMultiEditEnginePreview(unittest.TestCase):
    def test_preview_contains_diff(self):
        engine = MultiEditEngine("f.py", "hello\nworld").add_edit("hello", "hi")
        preview = engine.preview()
        self.assertIn("---", preview)
        self.assertIn("+++", preview)
        self.assertIn("-hello", preview)
        self.assertIn("+hi", preview)

    def test_preview_no_edits_empty(self):
        engine = MultiEditEngine("f.py", "hello")
        preview = engine.preview()
        self.assertEqual(preview, "")


if __name__ == "__main__":
    unittest.main()
