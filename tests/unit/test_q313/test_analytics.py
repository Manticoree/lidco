"""Tests for snapshot_test.analytics — SnapshotAnalytics."""

import tempfile
import time
import unittest
from unittest import mock

from lidco.snapshot_test.analytics import (
    SnapshotAnalytics,
    SnapshotStats,
    ChurnReport,
    SizeTrendEntry,
    StaleSnapshot,
)
from lidco.snapshot_test.manager import SnapshotManager


class TestAnalyticsBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.mgr = SnapshotManager(self._td.name)
        self.analytics = SnapshotAnalytics(self.mgr)

    def tearDown(self):
        self._td.cleanup()


class TestStats(TestAnalyticsBase):
    def test_empty_stats(self):
        st = self.analytics.stats()
        self.assertEqual(st.total_snapshots, 0)
        self.assertEqual(st.total_size_bytes, 0)
        self.assertEqual(st.avg_size_bytes, 0.0)

    def test_single_snapshot(self):
        self.mgr.create("s1", "hello")
        st = self.analytics.stats()
        self.assertEqual(st.total_snapshots, 1)
        self.assertEqual(st.total_size_bytes, 5)
        self.assertEqual(st.largest_name, "s1")
        self.assertEqual(st.smallest_name, "s1")

    def test_multiple_snapshots(self):
        self.mgr.create("small", "hi")
        self.mgr.create("big", "a" * 100)
        st = self.analytics.stats()
        self.assertEqual(st.total_snapshots, 2)
        self.assertEqual(st.largest_name, "big")
        self.assertEqual(st.smallest_name, "small")
        self.assertEqual(st.total_size_bytes, 2 + 100)

    def test_avg_size(self):
        self.mgr.create("a", "12345")
        self.mgr.create("b", "123")
        st = self.analytics.stats()
        self.assertAlmostEqual(st.avg_size_bytes, 4.0)


class TestChurn(TestAnalyticsBase):
    def test_empty(self):
        report = self.analytics.churn()
        self.assertEqual(report.entries, [])
        self.assertEqual(report.avg_updates, 0.0)

    def test_no_updates(self):
        self.mgr.create("s1", "data")
        report = self.analytics.churn()
        self.assertEqual(len(report.entries), 1)
        self.assertEqual(report.entries[0].update_count, 0)

    def test_with_update(self):
        self.mgr.create("s1", "v1")
        self.mgr.update("s1", "v2")
        report = self.analytics.churn()
        self.assertEqual(len(report.entries), 1)
        self.assertEqual(report.entries[0].update_count, 1)

    def test_most_and_least_churned(self):
        self.mgr.create("stable", "v1")
        self.mgr.create("volatile", "v1")
        self.mgr.update("volatile", "v2")
        report = self.analytics.churn()
        self.assertEqual(report.most_churned, "volatile")
        self.assertEqual(report.least_churned, "stable")


class TestSizeTrends(TestAnalyticsBase):
    def test_empty(self):
        self.assertEqual(self.analytics.size_trends(), [])

    def test_sorted_descending(self):
        self.mgr.create("small", "x")
        self.mgr.create("big", "x" * 50)
        trends = self.analytics.size_trends()
        self.assertEqual(len(trends), 2)
        self.assertEqual(trends[0].name, "big")

    def test_entry_fields(self):
        self.mgr.create("s1", "data")
        trends = self.analytics.size_trends()
        entry = trends[0]
        self.assertIsInstance(entry, SizeTrendEntry)
        self.assertEqual(entry.name, "s1")
        self.assertEqual(entry.size_bytes, 4)


class TestStaleSnapshots(TestAnalyticsBase):
    def test_no_stale(self):
        self.mgr.create("fresh", "data")
        stale = self.analytics.stale_snapshots(days=1)
        self.assertEqual(stale, [])

    def test_stale_detected(self):
        self.mgr.create("old", "data")
        # Patch the meta to look old
        rec = self.mgr.read("old")
        old_time = time.time() - 200 * 86400
        import json
        from pathlib import Path
        meta_p = self.mgr.snapshot_dir / "old.meta.json"
        meta_data = json.loads(meta_p.read_text())
        meta_data["updated_at"] = old_time
        meta_data["created_at"] = old_time
        meta_p.write_text(json.dumps(meta_data))

        stale = self.analytics.stale_snapshots(days=90)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0].name, "old")
        self.assertGreater(stale[0].age_days, 90)

    def test_default_threshold(self):
        self.assertEqual(SnapshotAnalytics.DEFAULT_STALE_DAYS, 90)


class TestOrphanedFiles(TestAnalyticsBase):
    def test_no_known_tests(self):
        self.mgr.create("s1", "data")
        orphans = self.analytics.orphaned_files()
        self.assertEqual(orphans, [])

    def test_orphan_detected(self):
        self.mgr.create("active", "data")
        self.mgr.create("orphan", "data")
        orphans = self.analytics.orphaned_files(known_tests=["active"])
        self.assertEqual(orphans, ["orphan"])

    def test_no_orphans(self):
        self.mgr.create("a", "data")
        orphans = self.analytics.orphaned_files(known_tests=["a"])
        self.assertEqual(orphans, [])

    def test_sorted_output(self):
        self.mgr.create("z", "d")
        self.mgr.create("a", "d")
        self.mgr.create("m", "d")
        orphans = self.analytics.orphaned_files(known_tests=[])
        self.assertEqual(orphans, ["a", "m", "z"])


if __name__ == "__main__":
    unittest.main()
