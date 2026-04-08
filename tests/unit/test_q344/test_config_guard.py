"""Tests for ConfigCorruptionGuard (Q344)."""
from __future__ import annotations

import os
import tempfile
import unittest


def _guard():
    from lidco.stability.config_guard import ConfigCorruptionGuard
    return ConfigCorruptionGuard()


class TestDetectCorruption(unittest.TestCase):
    def test_valid_json_returns_valid_true(self):
        result = _guard().detect_corruption('{"key": "value"}', "json")
        self.assertTrue(result["valid"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["format"], "json")

    def test_invalid_json_returns_valid_false(self):
        result = _guard().detect_corruption('{"key": }', "json")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])

    def test_empty_json_object_is_valid(self):
        result = _guard().detect_corruption("{}", "json")
        self.assertTrue(result["valid"])

    def test_truncated_json_marks_recoverable(self):
        # Error mid-string (not at end) — recoverable because content exists before error
        result = _guard().detect_corruption('{"a": 1, "b": }, "c": 3}', "json")
        self.assertFalse(result["valid"])
        self.assertTrue(result["recoverable"])

    def test_completely_empty_json_invalid(self):
        result = _guard().detect_corruption("", "json")
        self.assertFalse(result["valid"])

    def test_unsupported_format_returns_invalid(self):
        result = _guard().detect_corruption("data", "xml")
        self.assertFalse(result["valid"])
        self.assertIn("xml", result["error"].lower() or result["format"])

    def test_format_field_present_in_result(self):
        result = _guard().detect_corruption("{}", "json")
        self.assertIn("format", result)
        self.assertIn("recoverable", result)


class TestAtomicWrite(unittest.TestCase):
    def test_write_creates_file_with_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            result = _guard().atomic_write(path, '{"x": 1}')
            self.assertTrue(result["success"])
            self.assertEqual(result["path"], path)
            with open(path) as f:
                self.assertEqual(f.read(), '{"x": 1}')

    def test_write_returns_backup_path_for_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            # Create the file first
            with open(path, "w") as f:
                f.write('{"old": true}')
            result = _guard().atomic_write(path, '{"new": true}')
            self.assertTrue(result["success"])
            self.assertIsNotNone(result["backup_path"])
            self.assertTrue(os.path.exists(result["backup_path"]))

    def test_write_new_file_has_no_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "new_config.json")
            result = _guard().atomic_write(path, "data")
            self.assertTrue(result["success"])
            self.assertIsNone(result["backup_path"])


class TestBackupBeforeWrite(unittest.TestCase):
    def test_backup_of_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            content = '{"hello": "world"}'
            with open(path, "w") as f:
                f.write(content)
            result = _guard().backup_before_write(path)
            self.assertTrue(result["backed_up"])
            self.assertTrue(os.path.exists(result["backup_path"]))
            self.assertEqual(result["original_size"], len(content))

    def test_backup_of_nonexistent_file_returns_not_backed_up(self):
        result = _guard().backup_before_write("/nonexistent/path/config.json")
        self.assertFalse(result["backed_up"])
        self.assertEqual(result["original_size"], 0)


class TestRecover(unittest.TestCase):
    def test_recover_restores_file_from_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup = os.path.join(tmpdir, "config.json.bak")
            target = os.path.join(tmpdir, "config.json")
            with open(backup, "w") as f:
                f.write("recovered content")
            result = _guard().recover(target, backup)
            self.assertTrue(result["recovered"])
            self.assertEqual(result["path"], target)
            self.assertEqual(result["source"], backup)
            with open(target) as f:
                self.assertEqual(f.read(), "recovered content")

    def test_recover_missing_backup_returns_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _guard().recover(
                os.path.join(tmpdir, "config.json"),
                os.path.join(tmpdir, "missing.bak"),
            )
            self.assertFalse(result["recovered"])
