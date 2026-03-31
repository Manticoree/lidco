"""Tests for Q149 CLI commands."""
from __future__ import annotations
import asyncio
import json
import unittest
from lidco.cli.commands import q149_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ149Commands(unittest.TestCase):
    def setUp(self):
        q149_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q149_cmds.register(MockRegistry())
        self.handler = self.registered["complete"].handler

    def test_command_registered(self):
        self.assertIn("complete", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    # --- prefix ---

    def test_prefix_insert(self):
        result = _run(self.handler("prefix insert hello"))
        self.assertIn("Inserted", result)

    def test_prefix_insert_no_word(self):
        result = _run(self.handler("prefix insert"))
        self.assertIn("Usage", result)

    def test_prefix_search(self):
        _run(self.handler("prefix insert hello"))
        _run(self.handler("prefix insert help"))
        result = _run(self.handler("prefix search hel"))
        data = json.loads(result)
        self.assertIn("hello", data)

    def test_prefix_search_no_prefix(self):
        result = _run(self.handler("prefix search"))
        self.assertIn("Usage", result)

    def test_prefix_delete(self):
        _run(self.handler("prefix insert hello"))
        result = _run(self.handler("prefix delete hello"))
        self.assertIn("Deleted", result)

    def test_prefix_delete_missing(self):
        result = _run(self.handler("prefix delete nope"))
        self.assertIn("not found", result)

    def test_prefix_words(self):
        _run(self.handler("prefix insert abc"))
        result = _run(self.handler("prefix words"))
        data = json.loads(result)
        self.assertIn("abc", data)

    def test_prefix_size(self):
        _run(self.handler("prefix insert abc"))
        result = _run(self.handler("prefix size"))
        self.assertIn("1", result)

    def test_prefix_usage(self):
        result = _run(self.handler("prefix"))
        self.assertIn("Usage", result)

    # --- context ---

    def test_context_add(self):
        payload = json.dumps({"category": "command", "items": ["help", "history"]})
        result = _run(self.handler(f"context add {payload}"))
        self.assertIn("Added", result)

    def test_context_add_invalid(self):
        result = _run(self.handler("context add notjson"))
        self.assertIn("Usage", result)

    def test_context_complete(self):
        payload = json.dumps({"category": "symbol", "items": ["myFunc", "myVar"]})
        _run(self.handler(f"context add {payload}"))
        result = _run(self.handler("context complete my"))
        data = json.loads(result)
        self.assertTrue(len(data) > 0)

    def test_context_sources(self):
        payload = json.dumps({"category": "symbol", "items": ["x"]})
        _run(self.handler(f"context add {payload}"))
        result = _run(self.handler("context sources"))
        data = json.loads(result)
        self.assertIn("symbol", data)

    def test_context_remove(self):
        payload = json.dumps({"category": "symbol", "items": ["x"]})
        _run(self.handler(f"context add {payload}"))
        result = _run(self.handler("context remove symbol"))
        self.assertIn("Removed", result)

    def test_context_usage(self):
        result = _run(self.handler("context"))
        self.assertIn("Usage", result)

    # --- rank ---

    def test_rank_items(self):
        payload = json.dumps({"items": ["apple", "app"], "query": "app"})
        result = _run(self.handler(f"rank items {payload}"))
        data = json.loads(result)
        self.assertTrue(len(data) > 0)

    def test_rank_top(self):
        payload = json.dumps({"items": ["a", "b", "c"], "query": "a", "n": 1})
        result = _run(self.handler(f"rank top {payload}"))
        data = json.loads(result)
        self.assertEqual(len(data), 1)

    def test_rank_usage(self):
        result = _run(self.handler("rank"))
        self.assertIn("Usage", result)

    # --- cache ---

    def test_cache_stats(self):
        result = _run(self.handler("cache stats"))
        data = json.loads(result)
        self.assertIn("hits", data)

    def test_cache_put_get(self):
        payload = json.dumps({"prefix": "he", "results": ["hello"]})
        _run(self.handler(f"cache put {payload}"))
        result = _run(self.handler("cache get he"))
        data = json.loads(result)
        self.assertIn("hello", data)

    def test_cache_get_miss(self):
        result = _run(self.handler("cache get nope"))
        self.assertIn("miss", result.lower())

    def test_cache_invalidate(self):
        payload = json.dumps({"prefix": "he", "results": ["hello"]})
        _run(self.handler(f"cache put {payload}"))
        result = _run(self.handler("cache invalidate he"))
        self.assertIn("Invalidated", result)

    def test_cache_invalidate_all(self):
        result = _run(self.handler("cache invalidate"))
        self.assertIn("cleared", result.lower())

    def test_cache_evict(self):
        result = _run(self.handler("cache evict"))
        self.assertIn("Evicted", result)

    def test_cache_usage(self):
        result = _run(self.handler("cache"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
