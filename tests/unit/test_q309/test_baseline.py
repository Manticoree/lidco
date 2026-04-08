"""Tests for visual_test/baseline.py — BaselineManager."""

import tempfile
import time
import unittest
from pathlib import Path

from lidco.visual_test.baseline import (
    ApprovalRequest,
    BaselineEntry,
    BaselineManager,
    MergeResult,
)


class TestBaselineEntry(unittest.TestCase):
    def test_creation(self):
        e = BaselineEntry(
            name="home", branch="main", sha256="abc123",
            width=800, height=600, created_at=1000.0,
        )
        self.assertEqual(e.name, "home")
        self.assertEqual(e.branch, "main")
        self.assertTrue(e.approved)

    def test_frozen(self):
        e = BaselineEntry(name="x", branch="b", sha256="s", width=1, height=1, created_at=0.0)
        with self.assertRaises(AttributeError):
            e.name = "y"  # type: ignore[misc]

    def test_unapproved(self):
        e = BaselineEntry(
            name="x", branch="b", sha256="s", width=1, height=1,
            created_at=0.0, approved=False,
        )
        self.assertFalse(e.approved)


class TestApprovalRequest(unittest.TestCase):
    def test_creation(self):
        r = ApprovalRequest(
            name="home", branch="main",
            old_sha256="old", new_sha256="new",
            requested_at=1000.0, diff_percentage=5.0,
        )
        self.assertEqual(r.name, "home")
        self.assertEqual(r.diff_percentage, 5.0)


class TestMergeResult(unittest.TestCase):
    def test_creation(self):
        r = MergeResult(merged_count=3, skipped=["a"], errors=["b"])
        self.assertEqual(r.merged_count, 3)
        self.assertEqual(r.skipped, ["a"])
        self.assertEqual(r.errors, ["b"])


class TestBaselineManager(unittest.TestCase):
    def _make_mgr(self, tmp: str) -> BaselineManager:
        return BaselineManager(storage_dir=tmp)

    def test_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            self.assertEqual(mgr.storage_dir, Path(tmp))
            self.assertEqual(mgr.entries, {})

    def test_store_and_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            entry = mgr.store("home", "main", b"PNG_DATA", 800, 600)
            self.assertEqual(entry.name, "home")
            self.assertEqual(entry.branch, "main")
            self.assertTrue(entry.approved)
            self.assertGreater(len(entry.sha256), 0)

            retrieved = mgr.get("home", "main")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.name, "home")

    def test_get_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            self.assertIsNone(mgr.get("nope", "main"))

    def test_get_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            mgr.store("logo", "main", b"IMG_BYTES", 100, 50)
            data = mgr.get_image("logo", "main")
            self.assertEqual(data, b"IMG_BYTES")

    def test_get_image_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            self.assertIsNone(mgr.get_image("nope", "main"))

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            mgr.store("x", "main", b"data", 10, 10)
            self.assertTrue(mgr.delete("x", "main"))
            self.assertIsNone(mgr.get("x", "main"))

    def test_delete_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            self.assertFalse(mgr.delete("nope", "main"))

    def test_list_baselines(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            mgr.store("b", "main", b"1", 10, 10)
            mgr.store("a", "main", b"2", 10, 10)
            mgr.store("c", "dev", b"3", 10, 10)
            all_bl = mgr.list_baselines()
            self.assertEqual(len(all_bl), 3)
            self.assertEqual(all_bl[0].name, "a")  # sorted by name

    def test_list_baselines_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            mgr.store("a", "main", b"1", 10, 10)
            mgr.store("b", "dev", b"2", 10, 10)
            main_bl = mgr.list_baselines(branch="main")
            self.assertEqual(len(main_bl), 1)
            self.assertEqual(main_bl[0].branch, "main")

    def test_request_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            mgr.store("home", "main", b"old", 100, 100)
            req = mgr.request_approval("home", "main", "new_sha", diff_percentage=2.5)
            self.assertEqual(req.name, "home")
            self.assertEqual(req.new_sha256, "new_sha")
            self.assertEqual(len(mgr.pending_approvals), 1)

    def test_approve(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            mgr.store("home", "main", b"old", 100, 100)
            mgr.request_approval("home", "main", "new_sha")
            ok = mgr.approve("home", "main", approved_by="tester")
            self.assertTrue(ok)
            self.assertEqual(len(mgr.pending_approvals), 0)
            entry = mgr.get("home", "main")
            self.assertEqual(entry.sha256, "new_sha")
            self.assertEqual(entry.approved_by, "tester")

    def test_approve_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            self.assertFalse(mgr.approve("nope", "main"))

    def test_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            mgr.request_approval("home", "main", "sha")
            ok = mgr.reject("home", "main")
            self.assertTrue(ok)
            self.assertEqual(len(mgr.pending_approvals), 0)

    def test_reject_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            self.assertFalse(mgr.reject("nope", "main"))

    def test_merge_baselines(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            mgr.store("page1", "feature", b"img1", 100, 100)
            mgr.store("page2", "feature", b"img2", 100, 100)
            result = mgr.merge_baselines("feature", "main")
            self.assertEqual(result.merged_count, 2)
            self.assertIsNotNone(mgr.get("page1", "main"))
            self.assertIsNotNone(mgr.get("page2", "main"))

    def test_merge_skips_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            mgr.store("page1", "feature", b"same", 100, 100)
            mgr.store("page1", "main", b"same", 100, 100)
            result = mgr.merge_baselines("feature", "main")
            self.assertEqual(result.merged_count, 0)
            self.assertEqual(result.skipped, ["page1"])

    def test_persistence(self):
        """Index should survive re-instantiation."""
        with tempfile.TemporaryDirectory() as tmp:
            mgr1 = self._make_mgr(tmp)
            mgr1.store("home", "main", b"data", 100, 100)
            mgr2 = self._make_mgr(tmp)
            self.assertIsNotNone(mgr2.get("home", "main"))

    def test_store_unapproved(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = self._make_mgr(tmp)
            entry = mgr.store("x", "main", b"d", 10, 10, auto_approve=False)
            self.assertFalse(entry.approved)


if __name__ == "__main__":
    unittest.main()
