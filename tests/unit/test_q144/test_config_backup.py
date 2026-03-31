"""Tests for Q144 ConfigBackup."""
from __future__ import annotations

import time
import unittest

from lidco.config.config_backup import ConfigBackup, BackupEntry


class TestBackupEntry(unittest.TestCase):
    def test_fields(self):
        e = BackupEntry(id="abc", timestamp=1.0, version="1.0.0", data={"k": "v"})
        self.assertEqual(e.id, "abc")
        self.assertIsNone(e.label)

    def test_label(self):
        e = BackupEntry(id="abc", timestamp=1.0, version="1.0.0", data={}, label="prod")
        self.assertEqual(e.label, "prod")


class TestConfigBackup(unittest.TestCase):
    def setUp(self):
        self.bk = ConfigBackup(max_backups=5)

    # --- backup ---

    def test_backup_returns_entry(self):
        entry = self.bk.backup({"a": 1}, "1.0.0")
        self.assertIsInstance(entry, BackupEntry)
        self.assertEqual(entry.version, "1.0.0")
        self.assertEqual(entry.data, {"a": 1})

    def test_backup_with_label(self):
        entry = self.bk.backup({}, "1.0.0", label="pre-migration")
        self.assertEqual(entry.label, "pre-migration")

    def test_backup_deep_copies(self):
        data = {"nested": {"x": 1}}
        entry = self.bk.backup(data, "1.0.0")
        data["nested"]["x"] = 999
        self.assertEqual(entry.data["nested"]["x"], 1)

    def test_backup_unique_ids(self):
        e1 = self.bk.backup({}, "1.0.0")
        e2 = self.bk.backup({}, "1.0.0")
        self.assertNotEqual(e1.id, e2.id)

    # --- restore ---

    def test_restore_found(self):
        entry = self.bk.backup({"k": "v"}, "1.0.0")
        data = self.bk.restore(entry.id)
        self.assertEqual(data, {"k": "v"})

    def test_restore_not_found(self):
        self.assertIsNone(self.bk.restore("nonexistent"))

    def test_restore_deep_copies(self):
        entry = self.bk.backup({"a": [1, 2]}, "1.0.0")
        d1 = self.bk.restore(entry.id)
        d1["a"].append(3)
        d2 = self.bk.restore(entry.id)
        self.assertEqual(d2["a"], [1, 2])

    # --- list_backups ---

    def test_list_empty(self):
        self.assertEqual(self.bk.list_backups(), [])

    def test_list_newest_first(self):
        self.bk.backup({}, "1.0.0")
        time.sleep(0.01)
        self.bk.backup({}, "2.0.0")
        backups = self.bk.list_backups()
        self.assertEqual(backups[0].version, "2.0.0")
        self.assertEqual(backups[1].version, "1.0.0")

    # --- latest ---

    def test_latest_empty(self):
        self.assertIsNone(self.bk.latest())

    def test_latest_returns_newest(self):
        self.bk.backup({}, "1.0.0")
        time.sleep(0.01)
        e2 = self.bk.backup({}, "2.0.0")
        self.assertEqual(self.bk.latest().id, e2.id)

    # --- delete ---

    def test_delete_existing(self):
        entry = self.bk.backup({}, "1.0.0")
        self.assertTrue(self.bk.delete(entry.id))
        self.assertEqual(len(self.bk.list_backups()), 0)

    def test_delete_nonexistent(self):
        self.assertFalse(self.bk.delete("nope"))

    # --- cleanup ---

    def test_cleanup_enforces_max(self):
        for i in range(10):
            self.bk.backup({"i": i}, "1.0.0")
        self.assertLessEqual(len(self.bk.list_backups()), 5)

    def test_cleanup_keeps_newest(self):
        for i in range(10):
            self.bk.backup({"i": i}, "1.0.0")
            time.sleep(0.005)
        backups = self.bk.list_backups()
        # Should have the latest 5
        self.assertEqual(len(backups), 5)
        # Newest should be i=9
        self.assertEqual(backups[0].data["i"], 9)

    def test_default_max_backups(self):
        bk = ConfigBackup()
        self.assertEqual(bk._max_backups, 20)


if __name__ == "__main__":
    unittest.main()
