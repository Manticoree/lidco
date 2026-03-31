"""Tests for restore_planner — Q127."""
from __future__ import annotations
import unittest
from lidco.workspace.restore_planner import RestorePlanner, RestoreAction
from lidco.workspace.snapshot2 import FileSnapshot, WorkspaceSnapshot
from lidco.workspace.file_index import FileIndex


def make_snapshot(files: dict) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        id="test",
        label="test",
        created_at="now",
        files={k: FileSnapshot(path=k, content=v) for k, v in files.items()},
    )


class TestRestoreAction(unittest.TestCase):
    def test_creation(self):
        a = RestoreAction(path="x.py", action="write", reason="changed")
        self.assertEqual(a.path, "x.py")
        self.assertEqual(a.action, "write")
        self.assertEqual(a.reason, "changed")


class TestRestorePlanner(unittest.TestCase):
    def setUp(self):
        self.planner = RestorePlanner()

    def test_plan_write_when_changed(self):
        snap = make_snapshot({"a.py": "new_content"})
        idx = FileIndex()
        idx.index_file("a.py", "old_content")
        actions = self.planner.plan(snap, idx)
        writes = [a for a in actions if a.action == "write"]
        self.assertTrue(any(a.path == "a.py" for a in writes))

    def test_plan_skip_when_same(self):
        snap = make_snapshot({"a.py": "same"})
        idx = FileIndex()
        idx.index_file("a.py", "same")
        actions = self.planner.plan(snap, idx)
        skips = [a for a in actions if a.action == "skip"]
        self.assertTrue(any(a.path == "a.py" for a in skips))

    def test_plan_delete_when_not_in_snapshot(self):
        snap = make_snapshot({"a.py": "x"})
        idx = FileIndex()
        idx.index_file("a.py", "x")
        idx.index_file("orphan.py", "z")
        actions = self.planner.plan(snap, idx)
        deletes = [a for a in actions if a.action == "delete"]
        self.assertTrue(any(a.path == "orphan.py" for a in deletes))

    def test_plan_write_when_not_indexed(self):
        snap = make_snapshot({"new.py": "content"})
        idx = FileIndex()
        actions = self.planner.plan(snap, idx)
        writes = [a for a in actions if a.action == "write"]
        self.assertTrue(any(a.path == "new.py" for a in writes))

    def test_plan_empty_snapshot(self):
        snap = make_snapshot({})
        idx = FileIndex()
        idx.index_file("x.py", "y")
        actions = self.planner.plan(snap, idx)
        deletes = [a for a in actions if a.action == "delete"]
        self.assertTrue(any(a.path == "x.py" for a in deletes))

    def test_apply_calls_write(self):
        written = {}
        deleted = []

        def write_fn(path, content):
            written[path] = content

        def delete_fn(path):
            deleted.append(path)

        actions = [RestoreAction("a.py", "write", "changed")]
        result = self.planner.apply(actions, write_fn, delete_fn)
        self.assertTrue(result["a.py"])

    def test_apply_calls_delete(self):
        deleted = []

        def write_fn(path, content):
            pass

        def delete_fn(path):
            deleted.append(path)

        actions = [RestoreAction("old.py", "delete")]
        result = self.planner.apply(actions, write_fn, delete_fn)
        self.assertTrue(result["old.py"])
        self.assertIn("old.py", deleted)

    def test_apply_skip_returns_true(self):
        def write_fn(p, c): pass
        def delete_fn(p): pass

        actions = [RestoreAction("a.py", "skip")]
        result = self.planner.apply(actions, write_fn, delete_fn)
        self.assertTrue(result["a.py"])

    def test_apply_failure_returns_false(self):
        def write_fn(path, content):
            raise OSError("disk full")

        def delete_fn(p): pass

        actions = [RestoreAction("a.py", "write")]
        result = self.planner.apply(actions, write_fn, delete_fn)
        self.assertFalse(result["a.py"])

    def test_apply_returns_dict(self):
        def write_fn(p, c): pass
        def delete_fn(p): pass
        result = self.planner.apply([], write_fn, delete_fn)
        self.assertIsInstance(result, dict)

    def test_plan_all_skips_if_same(self):
        snap = make_snapshot({"a.py": "same", "b.py": "same2"})
        idx = FileIndex()
        idx.index_file("a.py", "same")
        idx.index_file("b.py", "same2")
        actions = self.planner.plan(snap, idx)
        for a in actions:
            self.assertEqual(a.action, "skip")

    def test_plan_mixed(self):
        snap = make_snapshot({"a.py": "v1", "b.py": "v2"})
        idx = FileIndex()
        idx.index_file("a.py", "v1")   # same
        idx.index_file("b.py", "old")  # changed
        idx.index_file("c.py", "z")    # extra (delete)
        actions = self.planner.plan(snap, idx)
        action_map = {a.path: a.action for a in actions}
        self.assertEqual(action_map["a.py"], "skip")
        self.assertEqual(action_map["b.py"], "write")
        self.assertEqual(action_map["c.py"], "delete")

    def test_plan_returns_list(self):
        snap = make_snapshot({})
        idx = FileIndex()
        self.assertIsInstance(self.planner.plan(snap, idx), list)


if __name__ == "__main__":
    unittest.main()
