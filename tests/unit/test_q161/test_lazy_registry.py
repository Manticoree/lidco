"""Tests for LazyToolRegistry (Task 919)."""
from __future__ import annotations

import unittest

from lidco.tools.lazy_registry import LazyToolEntry, LazyToolRegistry


class TestLazyToolEntry(unittest.TestCase):
    def test_resolved_false_when_no_schema(self):
        entry = LazyToolEntry(name="t", description="d")
        self.assertFalse(entry.resolved)

    def test_resolved_true_with_cached(self):
        entry = LazyToolEntry(name="t", description="d", _cached_schema={"x": 1})
        self.assertTrue(entry.resolved)


class TestRegisterStub(unittest.TestCase):
    def test_registers_lazy_entry(self):
        reg = LazyToolRegistry()
        reg.register_stub("foo", "Foo tool", lambda: {"type": "object"})
        self.assertIn("foo", reg.list_names())

    def test_stub_not_resolved(self):
        reg = LazyToolRegistry()
        reg.register_stub("bar", "Bar tool", lambda: {"type": "object"})
        stubs = reg.list_stubs()
        self.assertEqual(len(stubs), 1)
        self.assertFalse(stubs[0].resolved)


class TestRegisterFull(unittest.TestCase):
    def test_registers_eager_entry(self):
        reg = LazyToolRegistry()
        reg.register_full("baz", "Baz tool", {"type": "object"})
        self.assertIn("baz", reg.list_names())

    def test_full_is_resolved(self):
        reg = LazyToolRegistry()
        reg.register_full("baz", "Baz tool", {"type": "object"})
        stubs = reg.list_stubs()
        self.assertTrue(stubs[0].resolved)


class TestResolve(unittest.TestCase):
    def test_resolve_unknown_returns_none(self):
        reg = LazyToolRegistry()
        self.assertIsNone(reg.resolve("nope"))

    def test_resolve_stub_calls_schema_fn(self):
        calls = []

        def schema_fn():
            calls.append(1)
            return {"type": "object", "properties": {}}

        reg = LazyToolRegistry()
        reg.register_stub("tool1", "desc", schema_fn)
        schema = reg.resolve("tool1")
        self.assertEqual(schema, {"type": "object", "properties": {}})
        self.assertEqual(len(calls), 1)

    def test_resolve_caches(self):
        calls = []

        def schema_fn():
            calls.append(1)
            return {"type": "string"}

        reg = LazyToolRegistry()
        reg.register_stub("tool1", "desc", schema_fn)
        reg.resolve("tool1")
        reg.resolve("tool1")
        self.assertEqual(len(calls), 1)  # only called once

    def test_resolve_full_entry(self):
        reg = LazyToolRegistry()
        reg.register_full("f", "desc", {"k": "v"})
        self.assertEqual(reg.resolve("f"), {"k": "v"})


class TestSearch(unittest.TestCase):
    def test_search_by_name(self):
        reg = LazyToolRegistry()
        reg.register_full("file_read", "Read a file", {})
        reg.register_full("file_write", "Write a file", {})
        reg.register_full("git_status", "Git status", {})
        results = reg.search("file")
        self.assertEqual(len(results), 2)

    def test_search_by_description(self):
        reg = LazyToolRegistry()
        reg.register_full("tool_a", "Analyze code", {})
        reg.register_full("tool_b", "Run tests", {})
        results = reg.search("code")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "tool_a")

    def test_search_max_results(self):
        reg = LazyToolRegistry()
        for i in range(10):
            reg.register_full(f"tool_{i}", "common desc", {})
        results = reg.search("common", max_results=3)
        self.assertEqual(len(results), 3)

    def test_search_no_match(self):
        reg = LazyToolRegistry()
        reg.register_full("foo", "bar", {})
        results = reg.search("zzz")
        self.assertEqual(results, [])


class TestListAndStats(unittest.TestCase):
    def test_list_names_sorted(self):
        reg = LazyToolRegistry()
        reg.register_full("beta", "b", {})
        reg.register_full("alpha", "a", {})
        self.assertEqual(reg.list_names(), ["alpha", "beta"])

    def test_stats(self):
        reg = LazyToolRegistry()
        reg.register_full("a", "a", {})
        reg.register_stub("b", "b", lambda: {})
        s = reg.stats()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["resolved"], 1)
        self.assertEqual(s["pending"], 1)

    def test_stats_after_resolve(self):
        reg = LazyToolRegistry()
        reg.register_stub("x", "x", lambda: {"t": 1})
        reg.resolve("x")
        s = reg.stats()
        self.assertEqual(s["resolved"], 1)
        self.assertEqual(s["pending"], 0)


if __name__ == "__main__":
    unittest.main()
