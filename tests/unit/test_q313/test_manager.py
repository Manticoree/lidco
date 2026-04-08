"""Tests for snapshot_test.manager — SnapshotManager."""

import json
import os
import tempfile
import unittest

from lidco.snapshot_test.manager import SnapshotManager, SnapshotMeta, SnapshotRecord


class TestSnapshotManagerInit(unittest.TestCase):
    def test_creates_snapshot_dir(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SnapshotManager(td)
            self.assertTrue(mgr.snapshot_dir.exists())
            self.assertTrue(mgr.snapshot_dir.name == "__snapshots__")

    def test_snapshot_dir_property(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SnapshotManager(td)
            self.assertIn("__snapshots__", str(mgr.snapshot_dir))


class TestMakeName(unittest.TestCase):
    def test_basic(self):
        name = SnapshotManager.make_name("test_foo.py", "test_bar")
        self.assertEqual(name, "test_foo.py__test_bar")

    def test_with_index(self):
        name = SnapshotManager.make_name("test_foo.py", "test_bar", index=2)
        self.assertEqual(name, "test_foo.py__test_bar__2")

    def test_zero_index_omitted(self):
        name = SnapshotManager.make_name("test_foo.py", "test_bar", index=0)
        self.assertNotIn("__0", name)

    def test_sanitizes_slashes(self):
        name = SnapshotManager.make_name("path/to/test.py", "my test")
        self.assertNotIn("/", name)
        self.assertNotIn(" ", name)


class TestSerialize(unittest.TestCase):
    def test_string_passthrough(self):
        self.assertEqual(SnapshotManager.serialize("hello"), "hello")

    def test_bytes(self):
        self.assertEqual(SnapshotManager.serialize(b"hello"), "hello")

    def test_dict_json(self):
        result = SnapshotManager.serialize({"b": 2, "a": 1})
        parsed = json.loads(result)
        self.assertEqual(parsed, {"a": 1, "b": 2})

    def test_list_json(self):
        result = SnapshotManager.serialize([3, 1, 2])
        self.assertEqual(json.loads(result), [3, 1, 2])

    def test_non_serializable_falls_back_to_repr(self):
        result = SnapshotManager.serialize(object)
        self.assertIn("object", result)


class TestCRUD(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.mgr = SnapshotManager(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_create_returns_record(self):
        rec = self.mgr.create("snap1", "hello world")
        self.assertIsInstance(rec, SnapshotRecord)
        self.assertEqual(rec.name, "snap1")
        self.assertEqual(rec.content, "hello world")

    def test_create_writes_files(self):
        self.mgr.create("snap1", "data")
        snap_file = self.mgr.snapshot_dir / "snap1.snap"
        meta_file = self.mgr.snapshot_dir / "snap1.meta.json"
        self.assertTrue(snap_file.exists())
        self.assertTrue(meta_file.exists())

    def test_read_existing(self):
        self.mgr.create("snap1", "data")
        rec = self.mgr.read("snap1")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.content, "data")

    def test_read_nonexistent(self):
        self.assertIsNone(self.mgr.read("nope"))

    def test_update_existing(self):
        self.mgr.create("snap1", "v1")
        rec = self.mgr.update("snap1", "v2")
        self.assertEqual(rec.content, "v2")
        re_read = self.mgr.read("snap1")
        self.assertEqual(re_read.content, "v2")

    def test_update_preserves_created_at(self):
        r1 = self.mgr.create("snap1", "v1")
        r2 = self.mgr.update("snap1", "v2")
        self.assertEqual(r2.meta.created_at, r1.meta.created_at)

    def test_update_creates_if_missing(self):
        rec = self.mgr.update("new_snap", "val")
        self.assertEqual(rec.name, "new_snap")
        self.assertTrue(self.mgr.exists("new_snap"))

    def test_delete_existing(self):
        self.mgr.create("snap1", "data")
        self.assertTrue(self.mgr.delete("snap1"))
        self.assertFalse(self.mgr.exists("snap1"))

    def test_delete_nonexistent(self):
        self.assertFalse(self.mgr.delete("nope"))

    def test_list_snapshots(self):
        self.mgr.create("b_snap", "b")
        self.mgr.create("a_snap", "a")
        names = self.mgr.list_snapshots()
        self.assertEqual(names, ["a_snap", "b_snap"])

    def test_list_empty(self):
        self.assertEqual(self.mgr.list_snapshots(), [])

    def test_exists(self):
        self.assertFalse(self.mgr.exists("snap1"))
        self.mgr.create("snap1", "x")
        self.assertTrue(self.mgr.exists("snap1"))


class TestSnapshotMeta(unittest.TestCase):
    def test_meta_fields(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SnapshotManager(td)
            rec = mgr.create("m1", "content")
            meta = rec.meta
            self.assertEqual(meta.name, "m1")
            self.assertGreater(meta.created_at, 0)
            self.assertGreater(meta.updated_at, 0)
            self.assertEqual(meta.size_bytes, len("content".encode()))
            self.assertTrue(len(meta.content_hash) == 64)  # sha256 hex

    def test_meta_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SnapshotManager(td)
            mgr.create("rt", {"key": "value"})
            meta_path = mgr.snapshot_dir / "rt.meta.json"
            data = json.loads(meta_path.read_text())
            self.assertEqual(data["name"], "rt")
            self.assertIn("content_hash", data)


if __name__ == "__main__":
    unittest.main()
