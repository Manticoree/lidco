"""Tests for cache.cache_warmer — WarmResult, CacheWarmer."""
from __future__ import annotations

import unittest

from lidco.cache.cache_warmer import CacheWarmer, WarmResult
from lidco.cache.prompt_cache import PromptCache


class TestWarmResult(unittest.TestCase):
    def test_frozen(self):
        r = WarmResult(warmed=5, skipped=2, failed=0)
        with self.assertRaises(AttributeError):
            r.warmed = 10  # type: ignore[misc]

    def test_fields(self):
        r = WarmResult(3, 1, 0)
        self.assertEqual(r.warmed, 3)
        self.assertEqual(r.skipped, 1)
        self.assertEqual(r.failed, 0)

    def test_equality(self):
        a = WarmResult(1, 2, 3)
        b = WarmResult(1, 2, 3)
        self.assertEqual(a, b)


class TestCacheWarmer(unittest.TestCase):
    def _make_warmer(self):
        cache = PromptCache()
        return CacheWarmer(cache), cache

    def test_warm_empty(self):
        warmer, _ = self._make_warmer()
        result = warmer.warm(())
        self.assertEqual(result.warmed, 0)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.failed, 0)

    def test_warm_new_entries(self):
        warmer, cache = self._make_warmer()
        entries = (("k1", "v1"), ("k2", "v2"))
        result = warmer.warm(entries)
        self.assertEqual(result.warmed, 2)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(cache.get("k1"), "v1")
        self.assertEqual(cache.get("k2"), "v2")

    def test_warm_skips_existing(self):
        warmer, cache = self._make_warmer()
        cache.put("k1", "old")
        result = warmer.warm((("k1", "new"),))
        self.assertEqual(result.skipped, 1)
        self.assertEqual(result.warmed, 0)
        self.assertEqual(cache.get("k1"), "old")

    def test_warm_mixed(self):
        warmer, cache = self._make_warmer()
        cache.put("existing", "val")
        entries = (("existing", "new"), ("fresh", "val"))
        result = warmer.warm(entries)
        self.assertEqual(result.warmed, 1)
        self.assertEqual(result.skipped, 1)

    def test_predict_keys_empty(self):
        warmer, _ = self._make_warmer()
        self.assertEqual(warmer.predict_keys(()), ())

    def test_predict_keys_repeated(self):
        warmer, _ = self._make_warmer()
        history = ("a", "b", "a", "c", "b", "b")
        predicted = warmer.predict_keys(history)
        self.assertIn("a", predicted)
        self.assertIn("b", predicted)
        self.assertNotIn("c", predicted)

    def test_predict_keys_unique(self):
        warmer, _ = self._make_warmer()
        history = ("x", "y", "z")
        predicted = warmer.predict_keys(history)
        self.assertEqual(predicted, ())

    def test_predict_keys_returns_tuple(self):
        warmer, _ = self._make_warmer()
        result = warmer.predict_keys(("a", "a"))
        self.assertIsInstance(result, tuple)

    def test_warm_returns_warm_result(self):
        warmer, _ = self._make_warmer()
        result = warmer.warm((("k", "v"),))
        self.assertIsInstance(result, WarmResult)

    def test_warm_single_entry(self):
        warmer, cache = self._make_warmer()
        result = warmer.warm((("only", "one"),))
        self.assertEqual(result.warmed, 1)
        self.assertEqual(cache.get("only"), "one")

    def test_predict_all_repeated(self):
        warmer, _ = self._make_warmer()
        history = ("a", "a", "a")
        predicted = warmer.predict_keys(history)
        self.assertEqual(predicted, ("a",))

    def test_warm_after_predict(self):
        warmer, cache = self._make_warmer()
        keys = warmer.predict_keys(("a", "a", "b", "b"))
        entries = tuple((k, f"val_{k}") for k in keys)
        result = warmer.warm(entries)
        self.assertEqual(result.warmed, 2)

    def test_warm_many_entries(self):
        warmer, _ = self._make_warmer()
        entries = tuple((f"k{i}", f"v{i}") for i in range(50))
        result = warmer.warm(entries)
        self.assertEqual(result.warmed, 50)

    def test_predict_keys_preserves_order(self):
        warmer, _ = self._make_warmer()
        history = ("b", "a", "b", "a")
        predicted = warmer.predict_keys(history)
        # b appears first
        self.assertEqual(predicted[0], "b")

    def test_warm_result_different_not_equal(self):
        a = WarmResult(1, 0, 0)
        b = WarmResult(2, 0, 0)
        self.assertNotEqual(a, b)


class TestCacheWarmerAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.cache import cache_warmer

        self.assertIn("WarmResult", cache_warmer.__all__)
        self.assertIn("CacheWarmer", cache_warmer.__all__)


if __name__ == "__main__":
    unittest.main()
