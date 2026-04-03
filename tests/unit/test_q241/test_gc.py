"""Tests for lidco.session.gc — SessionGarbageCollector."""
from __future__ import annotations

import unittest

from lidco.session.gc import GCResult, SessionGarbageCollector
from lidco.session.persister import SessionPersister


class TestGCResult(unittest.TestCase):
    def test_defaults(self):
        r = GCResult()
        self.assertEqual(r.deleted_count, 0)
        self.assertEqual(r.freed_bytes, 0)
        self.assertEqual(r.archived, [])


class TestGarbageCollector(unittest.TestCase):
    def setUp(self):
        self.p = SessionPersister(":memory:")
        self.gc = SessionGarbageCollector(self.p)

    def tearDown(self):
        self.p.close()

    def test_collect_empty(self):
        result = self.gc.collect()
        self.assertEqual(result.deleted_count, 0)

    def test_collect_max_count(self):
        for i in range(5):
            self.p.save(f"s{i}", [{"role": "user"}])
        self.gc.set_retention(max_count=3)
        result = self.gc.collect()
        self.assertEqual(result.deleted_count, 2)
        self.assertEqual(len(self.p.list_sessions()), 3)

    def test_dry_run_does_not_delete(self):
        for i in range(5):
            self.p.save(f"s{i}", [{"role": "user"}])
        self.gc.set_retention(max_count=3)
        result = self.gc.dry_run()
        self.assertEqual(result.deleted_count, 2)
        self.assertEqual(len(self.p.list_sessions()), 5)

    def test_disk_usage(self):
        self.p.save("s1", [{"role": "user", "content": "hello"}])
        usage = self.gc.disk_usage()
        self.assertEqual(usage["total_sessions"], 1)
        self.assertGreater(usage["total_bytes"], 0)

    def test_archive(self):
        self.p.save("s1", [{"role": "user", "content": "hi"}])
        archive_str = self.gc.archive("s1")
        self.assertIn("s1", archive_str)
        self.assertFalse(self.p.exists("s1"))

    def test_archive_nonexistent(self):
        self.assertEqual(self.gc.archive("nope"), "")

    def test_disk_usage_empty(self):
        usage = self.gc.disk_usage()
        self.assertEqual(usage["total_sessions"], 0)
        self.assertEqual(usage["total_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
