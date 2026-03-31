"""Tests for ContextReconciler — reconcile agent context on external file changes."""
from __future__ import annotations

import unittest

from lidco.awareness.reconciler import (
    CachedFile,
    ContextReconciler,
    ReconciliationAction,
    ReconciliationResult,
)


class MockChange:
    """Minimal mock for file change objects."""

    def __init__(self, file_path: str, change_type: str, new_mtime: float | None = None):
        self.file_path = file_path
        self.change_type = change_type
        self.new_mtime = new_mtime


class TestContextReconciler(unittest.TestCase):
    def setUp(self):
        self.reconciler = ContextReconciler()

    def test_cache_file(self):
        self.reconciler.cache_file("/a.py", "print(1)", 100.0)
        cached = self.reconciler.get_cached("/a.py")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.content, "print(1)")
        self.assertEqual(cached.mtime, 100.0)

    def test_get_cached_returns_cached_file(self):
        self.reconciler.cache_file("/b.py", "data", 200.0)
        cached = self.reconciler.get_cached("/b.py")
        self.assertIsInstance(cached, CachedFile)
        self.assertEqual(cached.file_path, "/b.py")

    def test_get_cached_not_found(self):
        result = self.reconciler.get_cached("/nonexistent.py")
        self.assertIsNone(result)

    def test_mark_editing(self):
        self.reconciler.mark_editing("/a.py")
        self.assertIn("/a.py", self.reconciler.editing_files)

    def test_unmark_editing(self):
        self.reconciler.mark_editing("/a.py")
        self.reconciler.unmark_editing("/a.py")
        self.assertNotIn("/a.py", self.reconciler.editing_files)

    def test_editing_files_property_is_copy(self):
        self.reconciler.mark_editing("/a.py")
        files = self.reconciler.editing_files
        files.add("/b.py")
        self.assertNotIn("/b.py", self.reconciler.editing_files)

    def test_reconcile_modified_cached_file(self):
        self.reconciler.cache_file("/a.py", "old", 100.0)
        changes = [MockChange("/a.py", "modified", 200.0)]
        result = self.reconciler.reconcile(changes)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].action, "update")
        self.assertIn("/a.py", result.updated)
        self.assertEqual(result.conflicts, [])

    def test_reconcile_modified_editing_file_is_conflict(self):
        self.reconciler.cache_file("/a.py", "old", 100.0)
        self.reconciler.mark_editing("/a.py")
        changes = [MockChange("/a.py", "modified", 200.0)]
        result = self.reconciler.reconcile(changes)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].action, "warn_conflict")
        self.assertIn("/a.py", result.conflicts)
        self.assertEqual(result.updated, [])

    def test_reconcile_deleted_cached_file(self):
        self.reconciler.cache_file("/a.py", "old", 100.0)
        changes = [MockChange("/a.py", "deleted")]
        result = self.reconciler.reconcile(changes)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].action, "remove")
        self.assertIn("/a.py", result.removed)
        # Cache should be cleared for this file
        self.assertIsNone(self.reconciler.get_cached("/a.py"))

    def test_reconcile_created_file_not_cached(self):
        """Created file not in cache should produce no action."""
        changes = [MockChange("/new.py", "created", 300.0)]
        result = self.reconciler.reconcile(changes)
        self.assertEqual(len(result.actions), 0)
        self.assertEqual(result.updated, [])
        self.assertEqual(result.conflicts, [])

    def test_reconcile_empty_changes(self):
        result = self.reconciler.reconcile([])
        self.assertEqual(len(result.actions), 0)
        self.assertEqual(result.conflicts, [])
        self.assertEqual(result.updated, [])
        self.assertEqual(result.removed, [])

    def test_reconcile_multiple_changes(self):
        self.reconciler.cache_file("/a.py", "a", 100.0)
        self.reconciler.cache_file("/b.py", "b", 100.0)
        self.reconciler.mark_editing("/b.py")

        changes = [
            MockChange("/a.py", "modified", 200.0),
            MockChange("/b.py", "modified", 200.0),
        ]
        result = self.reconciler.reconcile(changes)
        self.assertEqual(len(result.actions), 2)
        self.assertIn("/a.py", result.updated)
        self.assertIn("/b.py", result.conflicts)

    def test_reconcile_deleted_not_cached(self):
        """Deleted file not in cache produces no action."""
        changes = [MockChange("/unknown.py", "deleted")]
        result = self.reconciler.reconcile(changes)
        self.assertEqual(len(result.actions), 0)

    def test_clear_cache(self):
        self.reconciler.cache_file("/a.py", "a", 100.0)
        self.reconciler.mark_editing("/b.py")
        self.reconciler.clear_cache()
        self.assertIsNone(self.reconciler.get_cached("/a.py"))
        self.assertEqual(self.reconciler.editing_files, set())

    def test_cache_overwrites(self):
        self.reconciler.cache_file("/a.py", "v1", 100.0)
        self.reconciler.cache_file("/a.py", "v2", 200.0)
        cached = self.reconciler.get_cached("/a.py")
        self.assertEqual(cached.content, "v2")
        self.assertEqual(cached.mtime, 200.0)

    def test_reconciliation_result_structure(self):
        result = ReconciliationResult(
            actions=[ReconciliationAction("/a.py", "update", "reason")],
            conflicts=["/b.py"],
            updated=["/a.py"],
            removed=[],
        )
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.conflicts, ["/b.py"])

    def test_cached_file_dataclass(self):
        cf = CachedFile(file_path="/x.py", content="data", mtime=99.0)
        self.assertEqual(cf.file_path, "/x.py")
        self.assertEqual(cf.content, "data")
        self.assertIsInstance(cf.read_at, float)

    def test_reconcile_editing_not_cached(self):
        """Editing file not in cache should still produce conflict."""
        self.reconciler.mark_editing("/a.py")
        changes = [MockChange("/a.py", "modified", 200.0)]
        result = self.reconciler.reconcile(changes)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].action, "warn_conflict")

    def test_multiple_mark_unmark(self):
        self.reconciler.mark_editing("/a.py")
        self.reconciler.mark_editing("/b.py")
        self.assertEqual(len(self.reconciler.editing_files), 2)
        self.reconciler.unmark_editing("/a.py")
        self.assertEqual(self.reconciler.editing_files, {"/b.py"})

    def test_unmark_nonexistent(self):
        """Unmarking a file that's not being edited should not error."""
        self.reconciler.unmark_editing("/nope.py")
        self.assertEqual(self.reconciler.editing_files, set())


if __name__ == "__main__":
    unittest.main()
