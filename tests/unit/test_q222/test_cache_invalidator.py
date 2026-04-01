"""Tests for lidco.tools.cache_invalidator."""
from __future__ import annotations

import unittest

from lidco.tools.cache_invalidator import CacheInvalidator, InvalidationEvent


class TestInvalidationEvent(unittest.TestCase):
    def test_frozen(self) -> None:
        ev = InvalidationEvent(path="/a.py")
        with self.assertRaises(AttributeError):
            ev.path = "/b.py"  # type: ignore[misc]

    def test_defaults(self) -> None:
        ev = InvalidationEvent(path="/a.py")
        self.assertEqual(ev.reason, "file_changed")
        self.assertEqual(ev.affected_keys, ())


class TestCacheInvalidator(unittest.TestCase):
    def test_watch_and_get_keys(self) -> None:
        inv = CacheInvalidator()
        inv.watch("/a.py", ["key1", "key2"])
        keys = inv.get_affected_keys("/a.py")
        self.assertEqual(keys, ["key1", "key2"])

    def test_watch_merges_keys(self) -> None:
        inv = CacheInvalidator()
        inv.watch("/a.py", ["k1"])
        inv.watch("/a.py", ["k2"])
        self.assertEqual(sorted(inv.get_affected_keys("/a.py")), ["k1", "k2"])

    def test_unwatch(self) -> None:
        inv = CacheInvalidator()
        inv.watch("/a.py", ["k1"])
        self.assertTrue(inv.unwatch("/a.py"))
        self.assertFalse(inv.unwatch("/a.py"))
        self.assertEqual(inv.get_affected_keys("/a.py"), [])

    def test_on_file_changed(self) -> None:
        inv = CacheInvalidator()
        inv.watch("/a.py", ["k1", "k2"])
        event = inv.on_file_changed("/a.py")
        self.assertEqual(event.path, "/a.py")
        self.assertEqual(set(event.affected_keys), {"k1", "k2"})

    def test_on_file_changed_unknown_path(self) -> None:
        inv = CacheInvalidator()
        event = inv.on_file_changed("/unknown.py")
        self.assertEqual(event.affected_keys, ())

    def test_batch_invalidate(self) -> None:
        inv = CacheInvalidator()
        inv.watch("/a.py", ["k1"])
        inv.watch("/b.py", ["k2"])
        events = inv.batch_invalidate(["/a.py", "/b.py"])
        self.assertEqual(len(events), 2)

    def test_get_events_limit(self) -> None:
        inv = CacheInvalidator()
        for i in range(10):
            inv.on_file_changed(f"/{i}.py")
        self.assertEqual(len(inv.get_events(limit=5)), 5)

    def test_clear(self) -> None:
        inv = CacheInvalidator()
        inv.watch("/a.py", ["k1"])
        inv.on_file_changed("/a.py")
        inv.clear()
        self.assertEqual(inv.get_affected_keys("/a.py"), [])
        self.assertEqual(inv.get_events(), [])

    def test_summary(self) -> None:
        inv = CacheInvalidator()
        inv.watch("/a.py", ["k1", "k2"])
        s = inv.summary()
        self.assertIn("CacheInvalidator", s)
        self.assertIn("1 watched", s)
        self.assertIn("2 cache keys", s)


if __name__ == "__main__":
    unittest.main()
