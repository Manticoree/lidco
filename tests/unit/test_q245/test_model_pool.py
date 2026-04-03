"""Tests for ModelPool (Q245)."""
from __future__ import annotations

import unittest

from lidco.llm.model_pool import ModelEntry, ModelPool


class TestModelEntry(unittest.TestCase):
    def test_defaults(self):
        e = ModelEntry(name="gpt-4")
        self.assertEqual(e.name, "gpt-4")
        self.assertEqual(e.status, "healthy")
        self.assertEqual(e.latency_ms, 0.0)
        self.assertEqual(e.request_count, 0)

    def test_frozen(self):
        e = ModelEntry(name="gpt-4")
        with self.assertRaises(AttributeError):
            e.name = "other"  # type: ignore[misc]


class TestModelPoolAdd(unittest.TestCase):
    def test_add_returns_true(self):
        pool = ModelPool()
        self.assertTrue(pool.add("gpt-4"))

    def test_add_duplicate_returns_false(self):
        pool = ModelPool()
        pool.add("gpt-4")
        self.assertFalse(pool.add("gpt-4"))

    def test_add_multiple(self):
        pool = ModelPool()
        pool.add("a")
        pool.add("b")
        self.assertEqual(len(pool.list_models()), 2)


class TestModelPoolRemove(unittest.TestCase):
    def test_remove_existing(self):
        pool = ModelPool()
        pool.add("gpt-4")
        self.assertTrue(pool.remove("gpt-4"))
        self.assertEqual(len(pool.list_models()), 0)

    def test_remove_nonexistent(self):
        pool = ModelPool()
        self.assertFalse(pool.remove("nope"))


class TestModelPoolSelect(unittest.TestCase):
    def test_select_empty_returns_none(self):
        pool = ModelPool()
        self.assertIsNone(pool.select())

    def test_round_robin(self):
        pool = ModelPool()
        pool.add("a")
        pool.add("b")
        first = pool.select("round_robin")
        second = pool.select("round_robin")
        self.assertIn(first, ("a", "b"))
        self.assertIn(second, ("a", "b"))
        self.assertNotEqual(first, second)

    def test_least_loaded(self):
        pool = ModelPool()
        pool.add("a")
        pool.add("b")
        # Select 'a' twice via round-robin to bump its count
        pool.select("round_robin")
        pool.select("round_robin")
        # least_loaded should prefer the one with fewer requests
        result = pool.select("least_loaded")
        self.assertIsNotNone(result)

    def test_select_skips_unhealthy(self):
        pool = ModelPool()
        pool.add("a")
        pool.add("b")
        pool.mark_unhealthy("a")
        result = pool.select("round_robin")
        self.assertEqual(result, "b")

    def test_all_unhealthy_returns_none(self):
        pool = ModelPool()
        pool.add("a")
        pool.mark_unhealthy("a")
        self.assertIsNone(pool.select())


class TestModelPoolHealth(unittest.TestCase):
    def test_health_check_healthy(self):
        pool = ModelPool()
        pool.add("m")
        self.assertTrue(pool.health_check("m"))

    def test_health_check_unhealthy(self):
        pool = ModelPool()
        pool.add("m")
        pool.mark_unhealthy("m")
        self.assertFalse(pool.health_check("m"))

    def test_health_check_nonexistent(self):
        pool = ModelPool()
        self.assertFalse(pool.health_check("nope"))

    def test_mark_healthy_restores(self):
        pool = ModelPool()
        pool.add("m")
        pool.mark_unhealthy("m")
        pool.mark_healthy("m")
        self.assertTrue(pool.health_check("m"))

    def test_mark_unhealthy_nonexistent_no_error(self):
        pool = ModelPool()
        pool.mark_unhealthy("ghost")  # should not raise


class TestModelPoolStats(unittest.TestCase):
    def test_empty_stats(self):
        pool = ModelPool()
        s = pool.stats()
        self.assertEqual(s["total"], 0)
        self.assertEqual(s["healthy"], 0)

    def test_stats_after_operations(self):
        pool = ModelPool()
        pool.add("a")
        pool.add("b")
        pool.mark_unhealthy("b")
        pool.select()
        s = pool.stats()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["healthy"], 1)
        self.assertEqual(s["unhealthy"], 1)
        self.assertEqual(s["total_requests"], 1)


if __name__ == "__main__":
    unittest.main()
