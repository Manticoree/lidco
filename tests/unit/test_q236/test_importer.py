"""Tests for teleport.importer."""
from __future__ import annotations

import unittest

from lidco.teleport.importer import ImportResult, ImportStatus, SessionImporter


class TestImportResult(unittest.TestCase):
    def test_frozen(self) -> None:
        r = ImportResult(status=ImportStatus.SUCCESS)
        with self.assertRaises(AttributeError):
            r.status = ImportStatus.FAILED  # type: ignore[misc]

    def test_defaults(self) -> None:
        r = ImportResult(status=ImportStatus.SUCCESS)
        self.assertEqual(r.messages_imported, 0)
        self.assertEqual(r.files_resolved, 0)
        self.assertEqual(r.conflicts, ())
        self.assertEqual(r.warnings, ())


class TestSessionImporter(unittest.TestCase):
    def setUp(self) -> None:
        self.imp = SessionImporter()

    def test_validate_schema_valid(self) -> None:
        data = {"session_id": "s1", "version": "1.0", "messages": []}
        errors = self.imp.validate_schema(data)
        self.assertEqual(errors, [])

    def test_validate_schema_missing_fields(self) -> None:
        errors = self.imp.validate_schema({})
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("session_id" in e for e in errors))

    def test_validate_schema_bad_version(self) -> None:
        data = {"session_id": "s1", "version": "99.0", "messages": []}
        errors = self.imp.validate_schema(data)
        self.assertTrue(any("version" in e for e in errors))

    def test_validate_schema_bad_messages_type(self) -> None:
        data = {"session_id": "s1", "version": "1.0", "messages": "not-a-list"}
        errors = self.imp.validate_schema(data)
        self.assertTrue(any("list" in e for e in errors))

    def test_import_snapshot_success(self) -> None:
        data = {"session_id": "s1", "version": "1.0", "messages": [{"role": "user", "content": "hi"}]}
        result = self.imp.import_snapshot(data)
        self.assertEqual(result.status, ImportStatus.SUCCESS)
        self.assertEqual(result.messages_imported, 1)

    def test_import_snapshot_failed_validation(self) -> None:
        result = self.imp.import_snapshot({})
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertGreater(len(result.warnings), 0)

    def test_resolve_conflicts_no_overlap(self) -> None:
        resolved, conflicts = self.imp.resolve_conflicts(["a.py"], ["b.py"])
        self.assertEqual(resolved, ["b.py"])
        self.assertEqual(conflicts, [])

    def test_resolve_conflicts_with_overlap(self) -> None:
        resolved, conflicts = self.imp.resolve_conflicts(["a.py", "b.py"], ["b.py", "c.py"])
        self.assertIn("b.py", conflicts)
        self.assertIn("c.py", resolved)

    def test_merge_messages_dedup(self) -> None:
        m1 = {"role": "user", "content": "hello"}
        local = [m1]
        remote = [m1, {"role": "assistant", "content": "hi"}]
        merged = self.imp.merge_messages(local, remote)
        self.assertEqual(len(merged), 2)

    def test_summary(self) -> None:
        r = ImportResult(status=ImportStatus.SUCCESS, messages_imported=5, files_resolved=2)
        s = self.imp.summary(r)
        self.assertIn("success", s)
        self.assertIn("5", s)
