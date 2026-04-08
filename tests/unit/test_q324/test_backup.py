"""Tests for lidco.dr.backup — BackupManager."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from lidco.dr.backup import (
    BackupDestination,
    BackupManager,
    BackupManifest,
    BackupResult,
    BackupStatus,
    BackupType,
    DestinationType,
    EncryptionConfig,
    RetentionPolicy,
)


class TestRetentionPolicy(unittest.TestCase):
    def test_defaults(self) -> None:
        rp = RetentionPolicy()
        self.assertEqual(rp.max_versions, 10)
        self.assertEqual(rp.max_age_days, 90)
        self.assertEqual(rp.min_versions, 1)

    def test_invalid_max_versions(self) -> None:
        with self.assertRaises(ValueError):
            RetentionPolicy(max_versions=0)

    def test_invalid_max_age(self) -> None:
        with self.assertRaises(ValueError):
            RetentionPolicy(max_age_days=0)

    def test_min_greater_than_max(self) -> None:
        with self.assertRaises(ValueError):
            RetentionPolicy(max_versions=2, min_versions=5)


class TestEncryptionConfig(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        ec = EncryptionConfig()
        self.assertFalse(ec.enabled)

    def test_enabled_requires_key(self) -> None:
        with self.assertRaises(ValueError):
            EncryptionConfig(enabled=True, key_id="")

    def test_valid_encryption(self) -> None:
        ec = EncryptionConfig(enabled=True, key_id="my-key")
        self.assertTrue(ec.enabled)
        self.assertEqual(ec.key_id, "my-key")


class TestBackupDestination(unittest.TestCase):
    def test_empty_path_raises(self) -> None:
        with self.assertRaises(ValueError):
            BackupDestination(destination_type=DestinationType.LOCAL, path="")

    def test_valid(self) -> None:
        bd = BackupDestination(destination_type=DestinationType.S3, path="s3://bucket")
        self.assertEqual(bd.destination_type, DestinationType.S3)


class TestBackupManifest(unittest.TestCase):
    def test_to_dict_roundtrip(self) -> None:
        m = BackupManifest(
            backup_id="abc123",
            backup_type=BackupType.FULL,
            source_path="/src",
            destination="/dst",
            created_at=1000.0,
            size_bytes=500,
            file_count=3,
            checksum="deadbeef",
        )
        d = m.to_dict()
        self.assertEqual(d["backup_id"], "abc123")
        self.assertEqual(d["backup_type"], "full")
        m2 = BackupManifest.from_dict(d)
        self.assertEqual(m2.backup_id, m.backup_id)
        self.assertEqual(m2.backup_type, m.backup_type)
        self.assertEqual(m2.size_bytes, m.size_bytes)


class TestBackupManager(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self._backup_dir = os.path.join(self._tmpdir, "backups")
        self._source_dir = os.path.join(self._tmpdir, "source")
        os.makedirs(self._source_dir)
        # Create sample files
        Path(self._source_dir, "a.txt").write_text("hello")
        Path(self._source_dir, "sub").mkdir()
        Path(self._source_dir, "sub", "b.txt").write_text("world")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _mgr(self, **kwargs) -> BackupManager:
        return BackupManager(base_dir=self._backup_dir, **kwargs)

    def test_full_backup(self) -> None:
        mgr = self._mgr()
        result = mgr.create_backup(self._source_dir)
        self.assertEqual(result.status, BackupStatus.COMPLETED)
        self.assertIsNotNone(result.manifest)
        self.assertEqual(result.manifest.file_count, 2)
        self.assertGreater(result.manifest.size_bytes, 0)
        self.assertEqual(result.manifest.backup_type, BackupType.FULL)

    def test_incremental_backup(self) -> None:
        mgr = self._mgr()
        r1 = mgr.create_backup(self._source_dir)
        self.assertEqual(r1.status, BackupStatus.COMPLETED)
        # Modify a file
        Path(self._source_dir, "a.txt").write_text("changed")
        r2 = mgr.create_backup(self._source_dir, backup_type=BackupType.INCREMENTAL)
        self.assertEqual(r2.status, BackupStatus.COMPLETED)
        self.assertEqual(r2.manifest.backup_type, BackupType.INCREMENTAL)
        # Only changed file should be backed up
        self.assertEqual(r2.manifest.file_count, 1)

    def test_incremental_no_parent_becomes_full(self) -> None:
        mgr = self._mgr()
        result = mgr.create_backup(self._source_dir, backup_type=BackupType.INCREMENTAL)
        self.assertEqual(result.status, BackupStatus.COMPLETED)
        self.assertEqual(result.manifest.backup_type, BackupType.FULL)

    def test_backup_nonexistent_source(self) -> None:
        mgr = self._mgr()
        result = mgr.create_backup("/nonexistent/path")
        self.assertEqual(result.status, BackupStatus.FAILED)
        self.assertIn("does not exist", result.error)

    def test_encrypted_backup(self) -> None:
        enc = EncryptionConfig(enabled=True, key_id="testkey")
        mgr = self._mgr(encryption=enc)
        result = mgr.create_backup(self._source_dir)
        self.assertEqual(result.status, BackupStatus.COMPLETED)
        self.assertTrue(result.manifest.encrypted)

    def test_restore(self) -> None:
        mgr = self._mgr()
        result = mgr.create_backup(self._source_dir)
        restore_dir = os.path.join(self._tmpdir, "restored")
        ok = mgr.restore(result.backup_id, restore_dir)
        self.assertTrue(ok)
        self.assertTrue(Path(restore_dir, "a.txt").exists())
        self.assertEqual(Path(restore_dir, "a.txt").read_text(), "hello")

    def test_restore_encrypted(self) -> None:
        enc = EncryptionConfig(enabled=True, key_id="testkey")
        mgr = self._mgr(encryption=enc)
        result = mgr.create_backup(self._source_dir)
        restore_dir = os.path.join(self._tmpdir, "restored")
        ok = mgr.restore(result.backup_id, restore_dir)
        self.assertTrue(ok)
        self.assertEqual(Path(restore_dir, "a.txt").read_text(), "hello")

    def test_restore_nonexistent_backup(self) -> None:
        mgr = self._mgr()
        ok = mgr.restore("nonexistent", "/tmp/nowhere")
        self.assertFalse(ok)

    def test_list_backups(self) -> None:
        mgr = self._mgr()
        mgr.create_backup(self._source_dir)
        mgr.create_backup(self._source_dir)
        self.assertEqual(len(mgr.list_backups()), 2)

    def test_retention_max_versions(self) -> None:
        retention = RetentionPolicy(max_versions=2, min_versions=1)
        mgr = self._mgr(retention=retention)
        mgr.create_backup(self._source_dir)
        mgr.create_backup(self._source_dir)
        mgr.create_backup(self._source_dir)
        removed = mgr.apply_retention()
        self.assertEqual(len(removed), 1)
        self.assertEqual(len(mgr.list_backups()), 2)

    def test_add_destination(self) -> None:
        mgr = self._mgr()
        dest = BackupDestination(
            destination_type=DestinationType.LOCAL,
            path=os.path.join(self._tmpdir, "extra_dest"),
        )
        mgr.add_destination(dest)
        self.assertEqual(len(mgr.destinations), 1)
        result = mgr.create_backup(self._source_dir)
        self.assertEqual(result.status, BackupStatus.COMPLETED)
        # Check files were copied
        extra = Path(self._tmpdir, "extra_dest")
        self.assertTrue(extra.exists())

    def test_get_manifest(self) -> None:
        mgr = self._mgr()
        result = mgr.create_backup(self._source_dir)
        m = mgr.get_manifest(result.backup_id)
        self.assertIsNotNone(m)
        self.assertEqual(m.backup_id, result.backup_id)

    def test_properties(self) -> None:
        mgr = self._mgr()
        self.assertIsInstance(mgr.retention, RetentionPolicy)
        self.assertIsInstance(mgr.encryption, EncryptionConfig)
        self.assertIsInstance(mgr.base_dir, Path)


if __name__ == "__main__":
    unittest.main()
