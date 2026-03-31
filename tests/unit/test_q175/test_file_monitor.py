"""Tests for FileMonitor — live file change detection via mtime polling."""
from __future__ import annotations

import os
import tempfile
import time
import unittest

from lidco.awareness.file_monitor import FileChange, FileMonitor, MonitorConfig


class TestMonitorConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = MonitorConfig()
        self.assertEqual(cfg.poll_interval, 1.0)
        self.assertEqual(cfg.debounce, 0.5)
        self.assertIn("*.pyc", cfg.ignore_patterns)
        self.assertIn("__pycache__/*", cfg.ignore_patterns)
        self.assertIn(".git/*", cfg.ignore_patterns)

    def test_custom_config(self):
        cfg = MonitorConfig(poll_interval=2.0, debounce=1.0, ignore_patterns=["*.log"])
        self.assertEqual(cfg.poll_interval, 2.0)
        self.assertEqual(cfg.debounce, 1.0)
        self.assertEqual(cfg.ignore_patterns, ["*.log"])


class TestFileMonitor(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, name: str, content: str = "hello") -> str:
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_root_dir_property(self):
        mon = FileMonitor(self.tmpdir)
        self.assertEqual(mon.root_dir, self.tmpdir)

    def test_config_property(self):
        cfg = MonitorConfig(poll_interval=3.0)
        mon = FileMonitor(self.tmpdir, config=cfg)
        self.assertEqual(mon.config.poll_interval, 3.0)

    def test_scan_initial_no_changes(self):
        """First scan populates mtimes but returns no changes."""
        self._write_file("a.py", "pass")
        mon = FileMonitor(self.tmpdir)
        changes = mon.scan()
        self.assertEqual(changes, [])

    def test_scan_detects_modified(self):
        path = self._write_file("a.py", "v1")
        mon = FileMonitor(self.tmpdir)
        mon.scan()  # baseline

        time.sleep(0.05)
        with open(path, "w") as f:
            f.write("v2")
        # Force different mtime
        os.utime(path, (time.time() + 1, time.time() + 1))

        changes = mon.scan()
        modified = [c for c in changes if c.change_type == "modified"]
        self.assertEqual(len(modified), 1)
        self.assertEqual(modified[0].file_path, path)

    def test_scan_detects_created(self):
        self._write_file("a.py", "v1")
        mon = FileMonitor(self.tmpdir)
        mon.scan()  # baseline

        new_path = self._write_file("b.py", "new")
        changes = mon.scan()
        created = [c for c in changes if c.change_type == "created"]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].file_path, new_path)

    def test_scan_detects_deleted(self):
        path = self._write_file("a.py", "v1")
        mon = FileMonitor(self.tmpdir)
        mon.scan()  # baseline

        os.remove(path)
        changes = mon.scan()
        deleted = [c for c in changes if c.change_type == "deleted"]
        self.assertEqual(len(deleted), 1)
        self.assertEqual(deleted[0].file_path, path)

    def test_scan_ignores_pyc(self):
        self._write_file("mod.pyc", "bytecode")
        mon = FileMonitor(self.tmpdir)
        mon.scan()  # baseline
        snap = mon.snapshot()
        pyc_files = [f for f in snap if f.endswith(".pyc")]
        self.assertEqual(pyc_files, [])

    def test_scan_ignores_pycache_dir(self):
        self._write_file("__pycache__/mod.cpython-313.pyc", "bytecode")
        mon = FileMonitor(self.tmpdir)
        mon.scan()
        snap = mon.snapshot()
        pycache_files = [f for f in snap if "__pycache__" in f]
        self.assertEqual(pycache_files, [])

    def test_callback_on_change(self):
        path = self._write_file("a.py", "v1")
        mon = FileMonitor(self.tmpdir)
        mon.scan()

        received = []
        mon.on_change(lambda c: received.append(c))

        self._write_file("b.py", "new")
        mon.scan()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].change_type, "created")

    def test_multiple_callbacks(self):
        self._write_file("a.py", "v1")
        mon = FileMonitor(self.tmpdir)
        mon.scan()

        r1, r2 = [], []
        mon.on_change(lambda c: r1.append(c))
        mon.on_change(lambda c: r2.append(c))

        self._write_file("b.py", "new")
        mon.scan()
        self.assertEqual(len(r1), 1)
        self.assertEqual(len(r2), 1)

    def test_callback_exception_does_not_break(self):
        self._write_file("a.py", "v1")
        mon = FileMonitor(self.tmpdir)
        mon.scan()

        def bad_cb(c):
            raise ValueError("oops")

        received = []
        mon.on_change(bad_cb)
        mon.on_change(lambda c: received.append(c))

        self._write_file("b.py", "new")
        changes = mon.scan()
        self.assertEqual(len(changes), 1)
        self.assertEqual(len(received), 1)

    def test_start_stop(self):
        mon = FileMonitor(self.tmpdir)
        self.assertFalse(mon.is_running)
        mon.start()
        self.assertTrue(mon.is_running)
        mon.stop()
        self.assertFalse(mon.is_running)

    def test_is_running_property(self):
        mon = FileMonitor(self.tmpdir)
        self.assertFalse(mon.is_running)

    def test_get_changes_accumulates(self):
        self._write_file("a.py", "v1")
        mon = FileMonitor(self.tmpdir)
        mon.scan()

        self._write_file("b.py", "new1")
        mon.scan()
        self._write_file("c.py", "new2")
        mon.scan()

        all_changes = mon.get_changes()
        self.assertEqual(len(all_changes), 2)

    def test_clear_changes(self):
        self._write_file("a.py", "v1")
        mon = FileMonitor(self.tmpdir)
        mon.scan()
        self._write_file("b.py", "new")
        mon.scan()
        self.assertTrue(len(mon.get_changes()) > 0)

        mon.clear_changes()
        self.assertEqual(len(mon.get_changes()), 0)

    def test_snapshot(self):
        p1 = self._write_file("a.py", "v1")
        p2 = self._write_file("b.py", "v2")
        mon = FileMonitor(self.tmpdir)
        mon.scan()
        snap = mon.snapshot()
        self.assertIn(p1, snap)
        self.assertIn(p2, snap)
        self.assertIsInstance(snap[p1], float)

    def test_empty_directory(self):
        mon = FileMonitor(self.tmpdir)
        changes = mon.scan()
        self.assertEqual(changes, [])
        self.assertEqual(mon.snapshot(), {})

    def test_nested_files(self):
        self._write_file("sub/deep/file.py", "nested")
        mon = FileMonitor(self.tmpdir)
        mon.scan()
        snap = mon.snapshot()
        nested = [f for f in snap if "deep" in f]
        self.assertEqual(len(nested), 1)

    def test_nonexistent_root(self):
        mon = FileMonitor("/nonexistent/path/xyz")
        changes = mon.scan()
        self.assertEqual(changes, [])

    def test_file_change_dataclass(self):
        fc = FileChange(file_path="/a.py", change_type="modified", old_mtime=1.0, new_mtime=2.0)
        self.assertEqual(fc.file_path, "/a.py")
        self.assertEqual(fc.change_type, "modified")
        self.assertEqual(fc.old_mtime, 1.0)
        self.assertEqual(fc.new_mtime, 2.0)
        self.assertIsInstance(fc.detected_at, float)


if __name__ == "__main__":
    unittest.main()
