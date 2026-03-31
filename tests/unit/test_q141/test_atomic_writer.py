"""Tests for AtomicWriter."""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, call

from lidco.resilience.atomic_writer import AtomicWriter, WriteResult


class TestAtomicWriter(unittest.TestCase):
    def setUp(self):
        self.written: dict[str, bytes] = {}
        self.files: dict[str, bytes] = {}

        def fake_write(path, data):
            self.written[path] = data
            self.files[path] = data

        def fake_rename(src, dst):
            if src not in self.files:
                raise FileNotFoundError(src)
            self.files[dst] = self.files.pop(src)

        def fake_remove(path):
            if path not in self.files:
                raise FileNotFoundError(path)
            del self.files[path]

        def fake_exists(path):
            return path in self.files

        def fake_read(path):
            if path not in self.files:
                raise FileNotFoundError(path)
            return self.files[path].decode("utf-8")

        def fake_copy(src, dst):
            if src not in self.files:
                raise FileNotFoundError(src)
            self.files[dst] = self.files[src]

        self.writer = AtomicWriter(
            _write_fn=fake_write,
            _rename_fn=fake_rename,
            _remove_fn=fake_remove,
            _exists_fn=fake_exists,
            _read_fn=fake_read,
            _copy_fn=fake_copy,
        )

    # --- write ---
    def test_write_success(self):
        result = self.writer.write("/tmp/test.txt", "hello")
        self.assertTrue(result.success)
        self.assertEqual(result.path, "/tmp/test.txt")

    def test_write_bytes_count(self):
        result = self.writer.write("/tmp/test.txt", "hello")
        self.assertEqual(result.bytes_written, 5)

    def test_write_stores_content(self):
        self.writer.write("/tmp/test.txt", "hello")
        self.assertEqual(self.files["/tmp/test.txt"], b"hello")

    def test_write_temp_cleaned_up(self):
        self.writer.write("/tmp/test.txt", "hello")
        self.assertNotIn("/tmp/test.txt.tmp", self.files)

    def test_write_utf8(self):
        result = self.writer.write("/tmp/test.txt", "cafe\u0301")
        self.assertTrue(result.success)
        self.assertGreater(result.bytes_written, 0)

    def test_write_failure_returns_false(self):
        def bad_write(path, data):
            raise IOError("disk full")
        w = AtomicWriter(_write_fn=bad_write)
        result = w.write("/tmp/test.txt", "hello")
        self.assertFalse(result.success)
        self.assertEqual(result.bytes_written, 0)

    def test_write_custom_encoding(self):
        result = self.writer.write("/tmp/test.txt", "hello", encoding="ascii")
        self.assertTrue(result.success)

    # --- write_json ---
    def test_write_json_success(self):
        result = self.writer.write_json("/tmp/data.json", {"key": "val"})
        self.assertTrue(result.success)

    def test_write_json_content(self):
        self.writer.write_json("/tmp/data.json", {"key": "val"})
        content = self.files["/tmp/data.json"].decode("utf-8")
        parsed = json.loads(content)
        self.assertEqual(parsed["key"], "val")

    def test_write_json_pretty(self):
        self.writer.write_json("/tmp/data.json", {"a": 1})
        content = self.files["/tmp/data.json"].decode("utf-8")
        self.assertIn("\n", content)  # pretty printed

    def test_write_json_sorted_keys(self):
        self.writer.write_json("/tmp/data.json", {"b": 2, "a": 1})
        content = self.files["/tmp/data.json"].decode("utf-8")
        a_pos = content.index('"a"')
        b_pos = content.index('"b"')
        self.assertLess(a_pos, b_pos)

    # --- write_with_backup ---
    def test_backup_creates_bak(self):
        self.files["/tmp/old.txt"] = b"old content"
        self.writer.write_with_backup("/tmp/old.txt", "new content")
        self.assertIn("/tmp/old.txt.bak", self.files)

    def test_backup_preserves_old(self):
        self.files["/tmp/old.txt"] = b"old content"
        self.writer.write_with_backup("/tmp/old.txt", "new content")
        self.assertEqual(self.files["/tmp/old.txt.bak"], b"old content")

    def test_backup_writes_new_content(self):
        self.files["/tmp/old.txt"] = b"old content"
        self.writer.write_with_backup("/tmp/old.txt", "new content")
        self.assertEqual(self.files["/tmp/old.txt"], b"new content")

    def test_backup_returns_backup_path(self):
        self.files["/tmp/old.txt"] = b"old"
        result = self.writer.write_with_backup("/tmp/old.txt", "new")
        self.assertEqual(result.backup_path, "/tmp/old.txt.bak")

    def test_backup_custom_suffix(self):
        self.files["/tmp/old.txt"] = b"old"
        self.writer.write_with_backup("/tmp/old.txt", "new", backup_suffix=".backup")
        self.assertIn("/tmp/old.txt.backup", self.files)

    def test_backup_no_existing_file(self):
        result = self.writer.write_with_backup("/tmp/new.txt", "content")
        self.assertTrue(result.success)
        self.assertIsNone(result.backup_path)

    # --- safe_delete ---
    def test_safe_delete_removes_file(self):
        self.files["/tmp/f.txt"] = b"data"
        result = self.writer.safe_delete("/tmp/f.txt")
        self.assertTrue(result)
        self.assertNotIn("/tmp/f.txt", self.files)

    def test_safe_delete_creates_backup(self):
        self.files["/tmp/f.txt"] = b"data"
        self.writer.safe_delete("/tmp/f.txt", backup=True)
        self.assertIn("/tmp/f.txt.bak", self.files)

    def test_safe_delete_no_backup(self):
        self.files["/tmp/f.txt"] = b"data"
        self.writer.safe_delete("/tmp/f.txt", backup=False)
        self.assertNotIn("/tmp/f.txt.bak", self.files)

    def test_safe_delete_nonexistent_returns_false(self):
        result = self.writer.safe_delete("/tmp/nope.txt")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
