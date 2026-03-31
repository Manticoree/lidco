"""Tests for PartialCollector."""
from __future__ import annotations

import asyncio
import time
import unittest

from lidco.resilience.partial_collector import (
    CollectionItem,
    CollectionResult,
    PartialCollector,
)


def _run(coro):
    return asyncio.run(coro)


class TestCollectionItem(unittest.TestCase):
    def test_success_item(self):
        item = CollectionItem(key="a", value=1)
        self.assertTrue(item.success)
        self.assertIsNone(item.error)

    def test_failure_item(self):
        item = CollectionItem(key="b", value=None, error="boom", success=False)
        self.assertFalse(item.success)
        self.assertEqual(item.error, "boom")


class TestCollectionResult(unittest.TestCase):
    def test_defaults(self):
        r = CollectionResult()
        self.assertEqual(r.items, [])
        self.assertEqual(r.succeeded, 0)
        self.assertEqual(r.failed, 0)
        self.assertFalse(r.partial)


class TestPartialCollector(unittest.TestCase):
    def test_all_succeed(self):
        c = PartialCollector()
        tasks = {"a": lambda: 1, "b": lambda: 2}
        result = c.collect(tasks)
        self.assertEqual(result.succeeded, 2)
        self.assertEqual(result.failed, 0)
        self.assertFalse(result.partial)

    def test_all_fail(self):
        c = PartialCollector()
        tasks = {
            "a": lambda: (_ for _ in ()).throw(RuntimeError("a")),
            "b": lambda: (_ for _ in ()).throw(ValueError("b")),
        }
        result = c.collect(tasks)
        self.assertEqual(result.succeeded, 0)
        self.assertEqual(result.failed, 2)
        self.assertFalse(result.partial)

    def test_partial(self):
        c = PartialCollector()
        tasks = {
            "ok": lambda: 42,
            "fail": lambda: (_ for _ in ()).throw(RuntimeError("x")),
        }
        result = c.collect(tasks)
        self.assertEqual(result.succeeded, 1)
        self.assertEqual(result.failed, 1)
        self.assertTrue(result.partial)

    def test_items_populated(self):
        c = PartialCollector()
        tasks = {"a": lambda: 10}
        result = c.collect(tasks)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].key, "a")
        self.assertEqual(result.items[0].value, 10)
        self.assertTrue(result.items[0].success)

    def test_failed_item_has_error(self):
        c = PartialCollector()
        tasks = {"x": lambda: (_ for _ in ()).throw(ValueError("val"))}
        result = c.collect(tasks)
        item = result.items[0]
        self.assertFalse(item.success)
        self.assertIn("val", item.error)

    def test_success_rate_all_ok(self):
        c = PartialCollector()
        c.collect({"a": lambda: 1, "b": lambda: 2})
        self.assertAlmostEqual(c.success_rate, 1.0)

    def test_success_rate_all_fail(self):
        c = PartialCollector()
        c.collect({"a": lambda: (_ for _ in ()).throw(RuntimeError("x"))})
        self.assertAlmostEqual(c.success_rate, 0.0)

    def test_success_rate_partial(self):
        c = PartialCollector()
        c.collect({
            "ok": lambda: 1,
            "fail": lambda: (_ for _ in ()).throw(RuntimeError("x")),
        })
        self.assertAlmostEqual(c.success_rate, 0.5)

    def test_success_rate_no_collection(self):
        c = PartialCollector()
        self.assertAlmostEqual(c.success_rate, 0.0)

    def test_empty_tasks(self):
        c = PartialCollector()
        result = c.collect({})
        self.assertEqual(result.succeeded, 0)
        self.assertEqual(result.failed, 0)
        self.assertEqual(len(result.items), 0)

    def test_collect_with_timeout_success(self):
        c = PartialCollector()
        tasks = {"fast": lambda: 42}
        result = c.collect_with_timeout(tasks, timeout=5.0)
        self.assertEqual(result.succeeded, 1)
        self.assertEqual(result.items[0].value, 42)

    def test_collect_with_timeout_timeout(self):
        c = PartialCollector()

        def slow():
            time.sleep(10)
            return "late"

        tasks = {"slow": slow}
        result = c.collect_with_timeout(tasks, timeout=0.1)
        self.assertEqual(result.failed, 1)
        self.assertIn("Timeout", result.items[0].error)

    def test_collect_with_timeout_error(self):
        c = PartialCollector()
        tasks = {"err": lambda: (_ for _ in ()).throw(ValueError("boom"))}
        result = c.collect_with_timeout(tasks, timeout=5.0)
        self.assertEqual(result.failed, 1)
        self.assertIn("boom", result.items[0].error)

    # --- Async tests ---

    def test_async_all_succeed(self):
        c = PartialCollector()

        async def a():
            return 1

        async def b():
            return 2

        result = _run(c.async_collect({"a": a, "b": b}))
        self.assertEqual(result.succeeded, 2)
        self.assertEqual(result.failed, 0)

    def test_async_partial(self):
        c = PartialCollector()

        async def ok():
            return 1

        async def fail():
            raise RuntimeError("x")

        result = _run(c.async_collect({"ok": ok, "fail": fail}))
        self.assertTrue(result.partial)

    def test_async_all_fail(self):
        c = PartialCollector()

        async def fail():
            raise RuntimeError("x")

        result = _run(c.async_collect({"a": fail}))
        self.assertEqual(result.failed, 1)
        self.assertFalse(result.partial)

    def test_async_items_populated(self):
        c = PartialCollector()

        async def fn():
            return 99

        result = _run(c.async_collect({"k": fn}))
        self.assertEqual(result.items[0].key, "k")
        self.assertEqual(result.items[0].value, 99)

    def test_async_updates_success_rate(self):
        c = PartialCollector()

        async def ok():
            return 1

        _run(c.async_collect({"a": ok}))
        self.assertAlmostEqual(c.success_rate, 1.0)

    def test_multiple_collects_update_rate(self):
        c = PartialCollector()
        c.collect({"a": lambda: 1})
        self.assertAlmostEqual(c.success_rate, 1.0)
        c.collect({"b": lambda: (_ for _ in ()).throw(RuntimeError("x"))})
        self.assertAlmostEqual(c.success_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
