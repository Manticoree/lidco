"""Tests for workspace/snapshot2 — Q127."""
from __future__ import annotations
import json
import os
import tempfile
import unittest
from lidco.workspace.snapshot2 import (
    FileSnapshot,
    WorkspaceSnapshot,
    WorkspaceSnapshotManager,
)


class TestFileSnapshot(unittest.TestCase):
    def test_creation(self):
        fs = FileSnapshot(path="a.py", content="x=1")
        self.assertEqual(fs.path, "a.py")
        self.assertEqual(fs.content, "x=1")
        self.assertEqual(fs.mtime, 0.0)
        self.assertEqual(fs.size, 0)


class TestWorkspaceSnapshot(unittest.TestCase):
    def test_file_count(self):
        snap = WorkspaceSnapshot(id="abc", label="test", created_at="now", files={
            "a.py": FileSnapshot("a.py", "x=1", size=3),
            "b.py": FileSnapshot("b.py", "y=2", size=3),
        })
        self.assertEqual(snap.file_count, 2)

    def test_total_size(self):
        snap = WorkspaceSnapshot(id="abc", label="test", created_at="now", files={
            "a.py": FileSnapshot("a.py", "x=1", size=3),
            "b.py": FileSnapshot("b.py", "yy=2", size=4),
        })
        self.assertEqual(snap.total_size, 7)

    def test_empty_snapshot(self):
        snap = WorkspaceSnapshot(id="x", label="", created_at="now", files={})
        self.assertEqual(snap.file_count, 0)
        self.assertEqual(snap.total_size, 0)


class TestWorkspaceSnapshotManager(unittest.TestCase):
    def setUp(self):
        self._files = {"a.py": "content of a", "b.py": "content of b"}

        def read_fn(path):
            return self._files.get(path)

        self.written = {}

        def write_fn(path, content):
            self.written[path] = content

        self.manager = WorkspaceSnapshotManager(read_fn=read_fn, write_fn=write_fn)

    def test_capture_returns_snapshot(self):
        snap = self.manager.capture(["a.py", "b.py"], label="v1")
        self.assertIsNotNone(snap)
        self.assertIsInstance(snap.id, str)

    def test_capture_label(self):
        snap = self.manager.capture(["a.py"], label="my_label")
        self.assertEqual(snap.label, "my_label")

    def test_capture_files(self):
        snap = self.manager.capture(["a.py", "b.py"])
        self.assertIn("a.py", snap.files)
        self.assertIn("b.py", snap.files)

    def test_capture_missing_file_skipped(self):
        snap = self.manager.capture(["missing.py"])
        self.assertNotIn("missing.py", snap.files)

    def test_restore_calls_write(self):
        snap = self.manager.capture(["a.py"])
        self.manager.restore(snap)
        self.assertIn("a.py", self.written)

    def test_restore_dry_run(self):
        snap = self.manager.capture(["a.py"])
        self.written.clear()
        result = self.manager.restore(snap, dry_run=True)
        self.assertTrue(result["a.py"])
        self.assertEqual(self.written, {})  # nothing actually written

    def test_restore_returns_dict(self):
        snap = self.manager.capture(["a.py"])
        result = self.manager.restore(snap)
        self.assertIsInstance(result, dict)

    def test_diff_added(self):
        snap_a = WorkspaceSnapshot(id="a", label="", created_at="now", files={
            "x.py": FileSnapshot("x.py", "x=1"),
        })
        snap_b = WorkspaceSnapshot(id="b", label="", created_at="now", files={
            "x.py": FileSnapshot("x.py", "x=1"),
            "y.py": FileSnapshot("y.py", "y=2"),
        })
        diff = self.manager.diff(snap_a, snap_b)
        self.assertIn("y.py", diff["added"])

    def test_diff_removed(self):
        snap_a = WorkspaceSnapshot(id="a", label="", created_at="now", files={
            "x.py": FileSnapshot("x.py", "x=1"),
            "old.py": FileSnapshot("old.py", "z=0"),
        })
        snap_b = WorkspaceSnapshot(id="b", label="", created_at="now", files={
            "x.py": FileSnapshot("x.py", "x=1"),
        })
        diff = self.manager.diff(snap_a, snap_b)
        self.assertIn("old.py", diff["removed"])

    def test_diff_modified(self):
        snap_a = WorkspaceSnapshot(id="a", label="", created_at="now", files={
            "x.py": FileSnapshot("x.py", "x=1"),
        })
        snap_b = WorkspaceSnapshot(id="b", label="", created_at="now", files={
            "x.py": FileSnapshot("x.py", "x=999"),
        })
        diff = self.manager.diff(snap_a, snap_b)
        self.assertIn("x.py", diff["modified"])

    def test_diff_unchanged(self):
        snap_a = WorkspaceSnapshot(id="a", label="", created_at="now", files={
            "x.py": FileSnapshot("x.py", "same"),
        })
        snap_b = WorkspaceSnapshot(id="b", label="", created_at="now", files={
            "x.py": FileSnapshot("x.py", "same"),
        })
        diff = self.manager.diff(snap_a, snap_b)
        self.assertIn("x.py", diff["unchanged"])

    def test_save_and_load(self):
        snap = self.manager.capture(["a.py"], label="saved")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.manager.save(snap, path)
            loaded = self.manager.load(path)
            self.assertEqual(loaded.id, snap.id)
            self.assertEqual(loaded.label, snap.label)
            self.assertIn("a.py", loaded.files)
        finally:
            os.unlink(path)

    def test_file_count_after_capture(self):
        snap = self.manager.capture(["a.py", "b.py"])
        self.assertEqual(snap.file_count, 2)

    def test_created_at_set(self):
        snap = self.manager.capture([])
        self.assertIsInstance(snap.created_at, str)
        self.assertTrue(len(snap.created_at) > 0)


if __name__ == "__main__":
    unittest.main()
