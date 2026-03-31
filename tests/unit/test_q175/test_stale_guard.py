"""Tests for StaleEditGuard — prevent edits to externally-modified files."""
from __future__ import annotations

import os
import tempfile
import time
import unittest

from lidco.awareness.stale_guard import GuardConfig, StaleCheckResult, StaleEditGuard


class TestGuardConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = GuardConfig()
        self.assertTrue(cfg.enabled)
        self.assertFalse(cfg.auto_rebase)

    def test_auto_rebase_config(self):
        cfg = GuardConfig(auto_rebase=True)
        self.assertTrue(cfg.auto_rebase)


class TestStaleEditGuard(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.guard = StaleEditGuard()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, name: str, content: str = "hello") -> str:
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_config_property(self):
        cfg = GuardConfig(enabled=False)
        guard = StaleEditGuard(config=cfg)
        self.assertFalse(guard.config.enabled)

    def test_disabled_returns_not_stale(self):
        guard = StaleEditGuard(config=GuardConfig(enabled=False))
        result = guard.check("/any/file.py")
        self.assertFalse(result.is_stale)
        self.assertEqual(result.message, "Stale check disabled")

    def test_untracked_file_not_stale(self):
        """File not previously read should not be considered stale."""
        result = self.guard.check("/some/file.py")
        self.assertFalse(result.is_stale)
        self.assertIn("not previously read", result.message)

    def test_check_not_stale(self):
        path = self._write_file("a.py", "data")
        mtime = os.path.getmtime(path)
        self.guard.record_read(path, mtime)
        result = self.guard.check(path)
        self.assertFalse(result.is_stale)
        self.assertEqual(result.read_mtime, mtime)
        self.assertEqual(result.current_mtime, mtime)
        self.assertEqual(result.message, "File is up to date")

    def test_check_stale(self):
        path = self._write_file("a.py", "v1")
        mtime = os.path.getmtime(path)
        self.guard.record_read(path, mtime)

        # Modify the file with a different mtime
        time.sleep(0.05)
        with open(path, "w") as f:
            f.write("v2")
        os.utime(path, (time.time() + 1, time.time() + 1))

        result = self.guard.check(path)
        self.assertTrue(result.is_stale)
        self.assertIn("modified since last read", result.message)

    def test_check_deleted_file_is_stale(self):
        path = self._write_file("a.py", "data")
        mtime = os.path.getmtime(path)
        self.guard.record_read(path, mtime)
        os.remove(path)

        result = self.guard.check(path)
        self.assertTrue(result.is_stale)
        self.assertIn("no longer exists", result.message)
        self.assertIsNone(result.current_mtime)

    def test_check_multiple(self):
        p1 = self._write_file("a.py", "a")
        p2 = self._write_file("b.py", "b")
        self.guard.record_read(p1, os.path.getmtime(p1))
        self.guard.record_read(p2, os.path.getmtime(p2))

        results = self.guard.check_multiple([p1, p2])
        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].is_stale)
        self.assertFalse(results[1].is_stale)

    def test_has_stale_files_true(self):
        p1 = self._write_file("a.py", "a")
        self.guard.record_read(p1, os.path.getmtime(p1))
        os.remove(p1)
        self.assertTrue(self.guard.has_stale_files([p1]))

    def test_has_stale_files_false(self):
        p1 = self._write_file("a.py", "a")
        self.guard.record_read(p1, os.path.getmtime(p1))
        self.assertFalse(self.guard.has_stale_files([p1]))

    def test_has_stale_files_none(self):
        self.assertFalse(self.guard.has_stale_files([]))

    def test_clear(self):
        self.guard.record_read("/a.py", 100.0)
        self.guard.clear()
        result = self.guard.check("/a.py")
        self.assertFalse(result.is_stale)
        self.assertIn("not previously read", result.message)

    def test_forget(self):
        self.guard.record_read("/a.py", 100.0)
        self.guard.record_read("/b.py", 200.0)
        self.guard.forget("/a.py")
        # /a.py forgotten
        result_a = self.guard.check("/a.py")
        self.assertIn("not previously read", result_a.message)
        # /b.py still tracked — would be stale since it doesn't exist on disk
        result_b = self.guard.check("/b.py")
        self.assertTrue(result_b.is_stale)

    def test_forget_nonexistent(self):
        """Forgetting unknown file should not error."""
        self.guard.forget("/nope.py")

    def test_record_read_overwrites(self):
        self.guard.record_read("/a.py", 100.0)
        self.guard.record_read("/a.py", 200.0)
        # Internal state updated
        result = self.guard.check("/a.py")
        # File doesn't exist on disk, so it's stale
        self.assertTrue(result.is_stale)
        self.assertEqual(result.read_mtime, 200.0)

    def test_stale_check_result_dataclass(self):
        r = StaleCheckResult(
            file_path="/x.py", is_stale=True,
            read_mtime=1.0, current_mtime=2.0,
            message="test",
        )
        self.assertEqual(r.file_path, "/x.py")
        self.assertTrue(r.is_stale)

    def test_check_multiple_mixed(self):
        p1 = self._write_file("ok.py", "fine")
        self.guard.record_read(p1, os.path.getmtime(p1))
        self.guard.record_read("/gone.py", 999.0)

        results = self.guard.check_multiple([p1, "/gone.py"])
        self.assertFalse(results[0].is_stale)
        self.assertTrue(results[1].is_stale)

    def test_has_stale_with_untracked(self):
        """Untracked files are not stale."""
        self.assertFalse(self.guard.has_stale_files(["/untracked.py"]))

    def test_default_guard_config(self):
        guard = StaleEditGuard()
        self.assertTrue(guard.config.enabled)
        self.assertFalse(guard.config.auto_rebase)


if __name__ == "__main__":
    unittest.main()
