"""Tests for Q135 ConnectionPool."""
from __future__ import annotations
import time
import unittest
from unittest.mock import patch
from lidco.network.connection_pool import ConnectionPool, Connection


class TestConnection(unittest.TestCase):
    def test_defaults(self):
        c = Connection()
        self.assertEqual(c.id, "")
        self.assertEqual(c.host, "")
        self.assertFalse(c.is_active)

    def test_custom(self):
        c = Connection(id="abc", host="localhost", is_active=True)
        self.assertTrue(c.is_active)


class TestConnectionPool(unittest.TestCase):
    def setUp(self):
        self.pool = ConnectionPool(max_size=3, max_idle_time=1.0)

    def test_acquire_creates_connection(self):
        conn = self.pool.acquire("example.com")
        self.assertTrue(conn.is_active)
        self.assertEqual(conn.host, "example.com")

    def test_acquire_reuses_idle(self):
        c1 = self.pool.acquire("a.com")
        self.pool.release(c1)
        c2 = self.pool.acquire("a.com")
        self.assertEqual(c1.id, c2.id)

    def test_acquire_different_host(self):
        c1 = self.pool.acquire("a.com")
        c2 = self.pool.acquire("b.com")
        self.assertNotEqual(c1.id, c2.id)

    def test_acquire_exhausted(self):
        for i in range(3):
            self.pool.acquire(f"host{i}.com")
        with self.assertRaises(RuntimeError):
            self.pool.acquire("extra.com")

    def test_release_marks_idle(self):
        conn = self.pool.acquire("x.com")
        self.pool.release(conn)
        self.assertFalse(conn.is_active)

    def test_close_removes(self):
        conn = self.pool.acquire("x.com")
        self.assertTrue(self.pool.close(conn.id))
        self.assertEqual(self.pool.stats()["total"], 0)

    def test_close_missing(self):
        self.assertFalse(self.pool.close("nonexistent"))

    def test_stats_empty(self):
        s = self.pool.stats()
        self.assertEqual(s, {"active": 0, "idle": 0, "total": 0})

    def test_stats_active(self):
        self.pool.acquire("a.com")
        s = self.pool.stats()
        self.assertEqual(s["active"], 1)
        self.assertEqual(s["total"], 1)

    def test_stats_idle(self):
        c = self.pool.acquire("a.com")
        self.pool.release(c)
        s = self.pool.stats()
        self.assertEqual(s["idle"], 1)
        self.assertEqual(s["active"], 0)

    def test_evict_idle_removes_old(self):
        c = self.pool.acquire("a.com")
        self.pool.release(c)
        # Manually set last_used to the past
        c.last_used = time.time() - 100
        count = self.pool.evict_idle()
        self.assertEqual(count, 1)
        self.assertEqual(self.pool.stats()["total"], 0)

    def test_evict_idle_keeps_recent(self):
        c = self.pool.acquire("a.com")
        self.pool.release(c)
        count = self.pool.evict_idle()
        self.assertEqual(count, 0)
        self.assertEqual(self.pool.stats()["total"], 1)

    def test_evict_idle_skips_active(self):
        c = self.pool.acquire("a.com")
        c.last_used = time.time() - 100
        count = self.pool.evict_idle()
        self.assertEqual(count, 0)

    def test_acquire_after_close_makes_room(self):
        c1 = self.pool.acquire("a.com")
        self.pool.acquire("b.com")
        self.pool.acquire("c.com")
        self.pool.close(c1.id)
        c4 = self.pool.acquire("d.com")
        self.assertEqual(c4.host, "d.com")

    def test_release_unknown_noop(self):
        fake = Connection(id="fake", host="x.com")
        self.pool.release(fake)  # should not raise

    def test_multiple_release(self):
        c = self.pool.acquire("a.com")
        self.pool.release(c)
        self.pool.release(c)  # idempotent
        self.assertFalse(c.is_active)

    def test_pool_default_sizes(self):
        p = ConnectionPool()
        self.assertEqual(p.max_size, 10)
        self.assertEqual(p.max_idle_time, 60.0)

    def test_connection_id_unique(self):
        ids = set()
        for i in range(3):
            c = self.pool.acquire(f"h{i}.com")
            ids.add(c.id)
        self.assertEqual(len(ids), 3)


if __name__ == "__main__":
    unittest.main()
