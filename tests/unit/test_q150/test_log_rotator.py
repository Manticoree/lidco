"""Tests for Q150 LogRotator."""
from __future__ import annotations

import time
import unittest

from lidco.logging.structured_logger import LogRecord
from lidco.logging.log_rotator import LogRotator, RotationPolicy, RotatedArchive


def _make_record(level="info", msg="test", ts=1.0) -> LogRecord:
    return LogRecord(level=level, message=msg, timestamp=ts, logger_name="app")


class TestRotationPolicy(unittest.TestCase):
    def test_defaults(self):
        p = RotationPolicy()
        self.assertEqual(p.max_records, 10000)
        self.assertEqual(p.max_age_seconds, 86400)

    def test_custom(self):
        p = RotationPolicy(max_records=100, max_age_seconds=60)
        self.assertEqual(p.max_records, 100)
        self.assertEqual(p.max_age_seconds, 60)


class TestRotatedArchive(unittest.TestCase):
    def test_fields(self):
        a = RotatedArchive(id="abc", records=[], created_at=1.0, record_count=0)
        self.assertEqual(a.id, "abc")
        self.assertEqual(a.record_count, 0)


class TestLogRotator(unittest.TestCase):
    def setUp(self):
        self.rotator = LogRotator(RotationPolicy(max_records=5, max_age_seconds=60))

    def test_default_policy(self):
        r = LogRotator()
        self.assertEqual(len(r.archives), 0)

    def test_should_rotate_by_count(self):
        records = [_make_record() for _ in range(5)]
        self.assertTrue(self.rotator.should_rotate(records, records[0].timestamp))

    def test_should_not_rotate_under_count(self):
        records = [_make_record() for _ in range(3)]
        self.assertFalse(self.rotator.should_rotate(records, time.time()))

    def test_should_rotate_by_age(self):
        old_ts = time.time() - 120  # 2 min ago, policy is 60s
        self.assertTrue(self.rotator.should_rotate([_make_record()], old_ts))

    def test_should_not_rotate_young(self):
        self.assertFalse(self.rotator.should_rotate([_make_record()], time.time()))

    def test_rotate_creates_archive(self):
        records = [_make_record(msg=f"m{i}") for i in range(3)]
        archive = self.rotator.rotate(records)
        self.assertEqual(archive.record_count, 3)
        self.assertEqual(len(archive.records), 3)
        self.assertIsInstance(archive.id, str)
        self.assertGreater(archive.created_at, 0)

    def test_rotate_serialises_records(self):
        records = [_make_record(msg="hello")]
        archive = self.rotator.rotate(records)
        self.assertEqual(archive.records[0]["message"], "hello")
        self.assertEqual(archive.records[0]["level"], "info")

    def test_archives_property(self):
        self.rotator.rotate([_make_record()])
        self.assertEqual(len(self.rotator.archives), 1)

    def test_archives_returns_copy(self):
        self.rotator.rotate([_make_record()])
        archives = self.rotator.archives
        archives.clear()
        self.assertEqual(len(self.rotator.archives), 1)

    def test_multiple_rotations(self):
        self.rotator.rotate([_make_record()])
        self.rotator.rotate([_make_record(), _make_record()])
        self.assertEqual(len(self.rotator.archives), 2)

    def test_total_archived(self):
        self.rotator.rotate([_make_record()])
        self.rotator.rotate([_make_record(), _make_record()])
        self.assertEqual(self.rotator.total_archived, 3)

    def test_total_archived_empty(self):
        self.assertEqual(self.rotator.total_archived, 0)

    def test_cleanup_removes_oldest(self):
        for _ in range(7):
            self.rotator.rotate([_make_record()])
        self.assertEqual(len(self.rotator.archives), 7)
        self.rotator.cleanup(max_archives=3)
        self.assertEqual(len(self.rotator.archives), 3)

    def test_cleanup_noop_under_limit(self):
        self.rotator.rotate([_make_record()])
        self.rotator.cleanup(max_archives=5)
        self.assertEqual(len(self.rotator.archives), 1)

    def test_cleanup_default(self):
        for _ in range(8):
            self.rotator.rotate([_make_record()])
        self.rotator.cleanup()
        self.assertEqual(len(self.rotator.archives), 5)

    def test_archive_has_unique_ids(self):
        a1 = self.rotator.rotate([_make_record()])
        a2 = self.rotator.rotate([_make_record()])
        self.assertNotEqual(a1.id, a2.id)

    def test_rotate_preserves_context(self):
        r = LogRecord(level="info", message="m", timestamp=1.0, logger_name="x", context={"k": "v"})
        archive = self.rotator.rotate([r])
        self.assertEqual(archive.records[0]["context"], {"k": "v"})

    def test_rotate_preserves_correlation(self):
        r = LogRecord(level="info", message="m", timestamp=1.0, logger_name="x", correlation_id="cid")
        archive = self.rotator.rotate([r])
        self.assertEqual(archive.records[0]["correlation_id"], "cid")

    def test_should_rotate_zero_timestamp(self):
        self.assertFalse(self.rotator.should_rotate([], 0))


if __name__ == "__main__":
    unittest.main()
