"""Tests for lidco.tools.file_cache."""
from __future__ import annotations

import unittest

from lidco.tools.file_cache import FileCacheEntry, FileReadCache


class TestFileCacheEntry(unittest.TestCase):
    def test_frozen(self) -> None:
        entry = FileCacheEntry(path="/a.py", content="x")
        with self.assertRaises(AttributeError):
            entry.path = "/b.py"  # type: ignore[misc]

    def test_defaults(self) -> None:
        entry = FileCacheEntry(path="/a.py", content="x")
        self.assertEqual(entry.mtime, 0.0)
        self.assertEqual(entry.size, 0)
        self.assertGreater(entry.cached_at, 0)


class TestFileReadCache(unittest.TestCase):
    def test_put_and_get(self) -> None:
        cache = FileReadCache()
        cache.put("/a.py", "content_a", mtime=100.0)
        self.assertEqual(cache.get("/a.py", current_mtime=100.0), "content_a")

    def test_get_miss(self) -> None:
        cache = FileReadCache()
        self.assertIsNone(cache.get("/nope.py"))
        self.assertEqual(cache.stats()["misses"], 1)

    def test_mtime_mismatch(self) -> None:
        cache = FileReadCache()
        cache.put("/a.py", "old", mtime=100.0)
        self.assertIsNone(cache.get("/a.py", current_mtime=200.0))

    def test_mtime_zero_always_hits(self) -> None:
        cache = FileReadCache()
        cache.put("/a.py", "content", mtime=100.0)
        self.assertEqual(cache.get("/a.py", current_mtime=0.0), "content")

    def test_invalidate(self) -> None:
        cache = FileReadCache()
        cache.put("/a.py", "x")
        self.assertTrue(cache.invalidate("/a.py"))
        self.assertFalse(cache.invalidate("/a.py"))

    def test_invalidate_by_prefix(self) -> None:
        cache = FileReadCache()
        cache.put("/src/a.py", "a")
        cache.put("/src/b.py", "b")
        cache.put("/tests/c.py", "c")
        removed = cache.invalidate_by_prefix("/src/")
        self.assertEqual(removed, 2)
        self.assertEqual(cache.stats()["entries"], 1)

    def test_preload(self) -> None:
        cache = FileReadCache()
        paths = ["/a.py", "/b.py", "/c.py"]
        contents = {"/a.py": "aa", "/b.py": "bb"}
        loaded = cache.preload(paths, contents)
        self.assertEqual(loaded, 2)
        self.assertEqual(cache.get("/a.py"), "aa")
        self.assertIsNone(cache.get("/c.py"))

    def test_max_entries_eviction(self) -> None:
        cache = FileReadCache(max_entries=3)
        for i in range(5):
            cache.put(f"/{i}.py", f"c{i}")
        self.assertLessEqual(cache.stats()["entries"], 3)

    def test_clear(self) -> None:
        cache = FileReadCache()
        cache.put("/a.py", "x")
        cache.clear()
        self.assertEqual(cache.stats()["entries"], 0)

    def test_summary(self) -> None:
        cache = FileReadCache()
        cache.put("/a.py", "x")
        cache.get("/a.py")
        s = cache.summary()
        self.assertIn("FileReadCache", s)
        self.assertIn("1 hits", s)


if __name__ == "__main__":
    unittest.main()
