"""Tests for Q135 CLI commands."""
from __future__ import annotations
import asyncio
import json
import unittest
from lidco.cli.commands import q135_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ135Commands(unittest.TestCase):
    def setUp(self):
        q135_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q135_cmds.register(MockRegistry())
        self.handler = self.registered["net"].handler

    def test_command_registered(self):
        self.assertIn("net", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    # --- parse ---

    def test_parse_url(self):
        result = _run(self.handler("parse https://example.com/path?q=1"))
        data = json.loads(result)
        self.assertEqual(data["scheme"], "https")
        self.assertEqual(data["host"], "example.com")
        self.assertEqual(data["query_params"]["q"], "1")

    def test_parse_no_url(self):
        result = _run(self.handler("parse"))
        self.assertIn("Usage", result)

    # --- build ---

    def test_build_url(self):
        result = _run(self.handler("build https example.com /api"))
        self.assertIn("example.com", result)
        self.assertIn("/api", result)

    def test_build_no_args(self):
        result = _run(self.handler("build"))
        self.assertIn("Usage", result)

    # --- valid ---

    def test_valid_true(self):
        result = _run(self.handler("valid https://example.com"))
        self.assertEqual(result, "True")

    def test_valid_false(self):
        result = _run(self.handler("valid example.com"))
        self.assertEqual(result, "False")

    def test_valid_no_args(self):
        result = _run(self.handler("valid"))
        self.assertIn("Usage", result)

    # --- headers ---

    def test_headers_set_and_get(self):
        _run(self.handler("headers set X-Key myvalue"))
        result = _run(self.handler("headers get X-Key"))
        self.assertEqual(result, "myvalue")

    def test_headers_get_missing(self):
        result = _run(self.handler("headers get Missing"))
        self.assertIn("not found", result.lower())

    def test_headers_remove(self):
        _run(self.handler("headers set X-Temp 1"))
        result = _run(self.handler("headers remove X-Temp"))
        self.assertIn("True", result)

    def test_headers_list(self):
        _run(self.handler("headers set A 1"))
        result = _run(self.handler("headers list"))
        data = json.loads(result)
        self.assertIn("A", data)

    def test_headers_set_missing_value(self):
        result = _run(self.handler("headers set OnlyName"))
        self.assertIn("Usage", result)

    def test_headers_no_sub(self):
        result = _run(self.handler("headers"))
        self.assertIn("Subcommands", result)

    # --- pool ---

    def test_pool_acquire(self):
        result = _run(self.handler("pool acquire example.com"))
        self.assertIn("Acquired", result)

    def test_pool_stats(self):
        result = _run(self.handler("pool stats"))
        data = json.loads(result)
        self.assertIn("total", data)

    def test_pool_evict(self):
        result = _run(self.handler("pool evict"))
        self.assertIn("Evicted", result)

    def test_pool_acquire_no_host(self):
        result = _run(self.handler("pool acquire"))
        self.assertIn("Usage", result)

    def test_pool_no_sub(self):
        result = _run(self.handler("pool"))
        self.assertIn("Subcommands", result)


if __name__ == "__main__":
    unittest.main()
