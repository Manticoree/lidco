"""Tests for editing.edit_planner — EditPlanner, FileEdit, EditGroup, EditPlan."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from lidco.editing.edit_planner import EditGroup, EditPlan, EditPlanner, FileEdit


class TestFileEdit(unittest.TestCase):
    def test_frozen(self):
        fe = FileEdit(old_text="a", new_text="b")
        with self.assertRaises(AttributeError):
            fe.old_text = "c"  # type: ignore[misc]

    def test_fields(self):
        fe = FileEdit(old_text="old", new_text="new")
        self.assertEqual(fe.old_text, "old")
        self.assertEqual(fe.new_text, "new")

    def test_equality(self):
        self.assertEqual(FileEdit("x", "y"), FileEdit("x", "y"))


class TestEditGroup(unittest.TestCase):
    def test_frozen(self):
        g = EditGroup(path="f.py", edits=())
        with self.assertRaises(AttributeError):
            g.path = "other"  # type: ignore[misc]

    def test_fields(self):
        edits = (FileEdit("a", "b"),)
        g = EditGroup(path="f.py", edits=edits)
        self.assertEqual(g.path, "f.py")
        self.assertEqual(len(g.edits), 1)


class TestEditPlan(unittest.TestCase):
    def test_frozen(self):
        plan = EditPlan(groups=(), total_edits=0)
        with self.assertRaises(AttributeError):
            plan.total_edits = 5  # type: ignore[misc]

    def test_fields(self):
        plan = EditPlan(groups=(), total_edits=0)
        self.assertEqual(plan.total_edits, 0)
        self.assertEqual(plan.groups, ())


class TestEditPlannerImmutability(unittest.TestCase):
    def test_add_file_edit_returns_new(self):
        p1 = EditPlanner()
        p2 = p1.add_file_edit("f.py", (FileEdit("a", "b"),))
        self.assertIsNot(p1, p2)
        self.assertEqual(len(p1.file_edits), 0)
        self.assertEqual(len(p2.file_edits), 1)

    def test_chain_adds(self):
        planner = (
            EditPlanner()
            .add_file_edit("a.py", (FileEdit("x", "y"),))
            .add_file_edit("b.py", (FileEdit("m", "n"),))
        )
        self.assertEqual(len(planner.file_edits), 2)


class TestEditPlannerPlan(unittest.TestCase):
    def test_empty_plan(self):
        plan = EditPlanner().plan()
        self.assertEqual(plan.total_edits, 0)
        self.assertEqual(plan.groups, ())

    def test_single_file(self):
        planner = EditPlanner().add_file_edit("f.py", (FileEdit("a", "b"), FileEdit("c", "d")))
        plan = planner.plan()
        self.assertEqual(plan.total_edits, 2)
        self.assertEqual(len(plan.groups), 1)
        self.assertEqual(plan.groups[0].path, "f.py")

    def test_multiple_files(self):
        planner = (
            EditPlanner()
            .add_file_edit("a.py", (FileEdit("x", "y"),))
            .add_file_edit("b.py", (FileEdit("m", "n"),))
        )
        plan = planner.plan()
        self.assertEqual(plan.total_edits, 2)
        self.assertEqual(len(plan.groups), 2)

    def test_merges_same_file(self):
        planner = (
            EditPlanner()
            .add_file_edit("f.py", (FileEdit("a", "b"),))
            .add_file_edit("f.py", (FileEdit("c", "d"),))
        )
        plan = planner.plan()
        self.assertEqual(plan.total_edits, 2)
        self.assertEqual(len(plan.groups), 1)
        self.assertEqual(len(plan.groups[0].edits), 2)


class TestEditPlannerValidate(unittest.TestCase):
    def test_empty_path_error(self):
        planner = EditPlanner().add_file_edit("", (FileEdit("a", "b"),))
        errors = planner.validate()
        self.assertTrue(any("Empty file path" in e for e in errors))

    def test_missing_file_error(self):
        planner = EditPlanner().add_file_edit("/nonexistent/abc.py", (FileEdit("a", "b"),))
        errors = planner.validate()
        self.assertTrue(any("not found" in e for e in errors))

    def test_valid_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("hello world")
            f.flush()
            path = f.name
        try:
            planner = EditPlanner().add_file_edit(path, (FileEdit("hello", "hi"),))
            errors = planner.validate()
            self.assertEqual(errors, ())
        finally:
            os.unlink(path)

    def test_old_text_not_found(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("hello")
            f.flush()
            path = f.name
        try:
            planner = EditPlanner().add_file_edit(path, (FileEdit("missing", "x"),))
            errors = planner.validate()
            self.assertTrue(any("not found" in e for e in errors))
        finally:
            os.unlink(path)

    def test_ambiguous_old_text(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("aaa")
            f.flush()
            path = f.name
        try:
            planner = EditPlanner().add_file_edit(path, (FileEdit("a", "b"),))
            errors = planner.validate()
            self.assertTrue(any("ambiguous" in e for e in errors))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
