"""Tests for change_tracker — Q127."""
from __future__ import annotations
import unittest
from lidco.workspace.change_tracker import ChangeTracker, FileChange


class TestFileChange(unittest.TestCase):
    def test_creation(self):
        c = FileChange(path="x.py", kind="added")
        self.assertEqual(c.path, "x.py")
        self.assertEqual(c.kind, "added")
        self.assertEqual(c.old_content, "")
        self.assertEqual(c.new_content, "")

    def test_with_content(self):
        c = FileChange(path="x.py", kind="modified", old_content="a", new_content="b")
        self.assertEqual(c.old_content, "a")
        self.assertEqual(c.new_content, "b")


class TestChangeTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = ChangeTracker()

    def test_empty_changes(self):
        self.assertEqual(self.tracker.changes(), [])

    def test_record(self):
        self.tracker.record(FileChange("a.py", "added"))
        self.assertEqual(len(self.tracker.changes()), 1)

    def test_changed_paths(self):
        self.tracker.record(FileChange("a.py", "added"))
        self.tracker.record(FileChange("b.py", "modified"))
        paths = self.tracker.changed_paths()
        self.assertIn("a.py", paths)
        self.assertIn("b.py", paths)

    def test_changed_paths_deduplication(self):
        self.tracker.record(FileChange("a.py", "modified"))
        self.tracker.record(FileChange("a.py", "modified"))
        self.assertEqual(len(self.tracker.changed_paths()), 1)

    def test_undo_returns_change(self):
        change = FileChange("a.py", "added")
        self.tracker.record(change)
        result = self.tracker.undo("a.py")
        self.assertIsNotNone(result)
        self.assertEqual(result.path, "a.py")

    def test_undo_removes_from_changes(self):
        self.tracker.record(FileChange("a.py", "added"))
        self.tracker.undo("a.py")
        self.assertEqual(self.tracker.changes(), [])

    def test_undo_missing_returns_none(self):
        result = self.tracker.undo("nonexistent.py")
        self.assertIsNone(result)

    def test_undo_pops_last_for_path(self):
        self.tracker.record(FileChange("a.py", "added", new_content="v1"))
        self.tracker.record(FileChange("a.py", "modified", new_content="v2"))
        result = self.tracker.undo("a.py")
        self.assertEqual(result.new_content, "v2")
        self.assertEqual(len(self.tracker.changes()), 1)

    def test_clear(self):
        self.tracker.record(FileChange("a.py", "added"))
        self.tracker.clear()
        self.assertEqual(self.tracker.changes(), [])

    def test_summary_empty(self):
        s = self.tracker.summary()
        self.assertEqual(s, {"added": 0, "modified": 0, "deleted": 0})

    def test_summary_counts(self):
        self.tracker.record(FileChange("a.py", "added"))
        self.tracker.record(FileChange("b.py", "added"))
        self.tracker.record(FileChange("c.py", "modified"))
        self.tracker.record(FileChange("d.py", "deleted"))
        s = self.tracker.summary()
        self.assertEqual(s["added"], 2)
        self.assertEqual(s["modified"], 1)
        self.assertEqual(s["deleted"], 1)

    def test_record_multiple_kinds(self):
        for kind in ("added", "modified", "deleted"):
            self.tracker.record(FileChange(f"{kind}.py", kind))
        self.assertEqual(len(self.tracker.changes()), 3)

    def test_changes_returns_copy(self):
        self.tracker.record(FileChange("a.py", "added"))
        copy = self.tracker.changes()
        copy.clear()
        self.assertEqual(len(self.tracker.changes()), 1)

    def test_undo_only_removes_one(self):
        self.tracker.record(FileChange("a.py", "added"))
        self.tracker.record(FileChange("a.py", "modified"))
        self.tracker.record(FileChange("b.py", "added"))
        self.tracker.undo("a.py")
        self.assertEqual(len(self.tracker.changes()), 2)

    def test_changed_paths_order(self):
        self.tracker.record(FileChange("z.py", "added"))
        self.tracker.record(FileChange("a.py", "added"))
        paths = self.tracker.changed_paths()
        self.assertEqual(paths[0], "z.py")  # insertion order

    def test_summary_keys_present(self):
        s = self.tracker.summary()
        for key in ("added", "modified", "deleted"):
            self.assertIn(key, s)


if __name__ == "__main__":
    unittest.main()
