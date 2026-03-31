"""Tests for file_index — Q127."""
from __future__ import annotations
import unittest
from lidco.workspace.file_index import FileIndex, IndexEntry


class TestIndexEntry(unittest.TestCase):
    def test_creation(self):
        e = IndexEntry(path="a.py", size=10, mtime=1.0, content_hash="abc")
        self.assertEqual(e.path, "a.py")
        self.assertEqual(e.size, 10)
        self.assertEqual(e.content_hash, "abc")


class TestFileIndex(unittest.TestCase):
    def setUp(self):
        self.idx = FileIndex()

    def test_empty(self):
        self.assertEqual(len(self.idx), 0)

    def test_index_file(self):
        entry = self.idx.index_file("a.py", "hello world")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.path, "a.py")

    def test_index_file_size(self):
        entry = self.idx.index_file("a.py", "hello")
        self.assertEqual(entry.size, len("hello".encode("utf-8")))

    def test_index_file_hash_set(self):
        entry = self.idx.index_file("a.py", "x = 1")
        self.assertIsInstance(entry.content_hash, str)
        self.assertTrue(len(entry.content_hash) > 0)

    def test_index_file_mtime(self):
        entry = self.idx.index_file("a.py", "x", mtime=12345.0)
        self.assertEqual(entry.mtime, 12345.0)

    def test_get_returns_entry(self):
        self.idx.index_file("b.py", "y = 2")
        result = self.idx.get("b.py")
        self.assertIsNotNone(result)
        self.assertEqual(result.path, "b.py")

    def test_get_missing(self):
        self.assertIsNone(self.idx.get("missing.py"))

    def test_has_changed_same_content(self):
        self.idx.index_file("a.py", "same content")
        self.assertFalse(self.idx.has_changed("a.py", "same content"))

    def test_has_changed_different_content(self):
        self.idx.index_file("a.py", "old")
        self.assertTrue(self.idx.has_changed("a.py", "new"))

    def test_has_changed_not_indexed(self):
        self.assertTrue(self.idx.has_changed("unknown.py", "anything"))

    def test_remove_existing(self):
        self.idx.index_file("a.py", "x")
        result = self.idx.remove("a.py")
        self.assertTrue(result)
        self.assertEqual(len(self.idx), 0)

    def test_remove_missing(self):
        result = self.idx.remove("nonexistent.py")
        self.assertFalse(result)

    def test_list_paths(self):
        self.idx.index_file("a.py", "x")
        self.idx.index_file("b.py", "y")
        paths = self.idx.list_paths()
        self.assertIn("a.py", paths)
        self.assertIn("b.py", paths)

    def test_clear(self):
        self.idx.index_file("a.py", "x")
        self.idx.clear()
        self.assertEqual(len(self.idx), 0)

    def test_len(self):
        self.idx.index_file("a.py", "x")
        self.idx.index_file("b.py", "y")
        self.assertEqual(len(self.idx), 2)

    def test_custom_hash_fn(self):
        custom = FileIndex(hash_fn=lambda c: "fixed_hash")
        entry = custom.index_file("a.py", "anything")
        self.assertEqual(entry.content_hash, "fixed_hash")

    def test_custom_hash_has_changed(self):
        custom = FileIndex(hash_fn=lambda c: c[:3])
        custom.index_file("a.py", "hello")
        self.assertFalse(custom.has_changed("a.py", "hel"))  # same 3-char prefix
        self.assertTrue(custom.has_changed("a.py", "world"))

    def test_list_paths_empty(self):
        self.assertEqual(self.idx.list_paths(), [])

    def test_reindex_updates_hash(self):
        self.idx.index_file("a.py", "v1")
        self.idx.index_file("a.py", "v2")
        self.assertFalse(self.idx.has_changed("a.py", "v2"))
        self.assertTrue(self.idx.has_changed("a.py", "v1"))

    def test_sha256_hash_deterministic(self):
        e1 = self.idx.index_file("a.py", "hello")
        e2 = self.idx.index_file("b.py", "hello")
        self.assertEqual(e1.content_hash, e2.content_hash)


if __name__ == "__main__":
    unittest.main()
