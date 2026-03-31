"""Tests for Q150 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest

from lidco.cli.commands import q150_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ150Commands(unittest.TestCase):
    def setUp(self):
        q150_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q150_cmds.register(MockRegistry())
        self.handler = self.registered["log"].handler

    def test_command_registered(self):
        self.assertIn("log", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("foobar"))
        self.assertIn("Usage", result)

    # --- write ---

    def test_write_info(self):
        result = _run(self.handler("write info hello world"))
        self.assertIn("[INFO]", result)
        self.assertIn("hello world", result)

    def test_write_error(self):
        result = _run(self.handler("write error something broke"))
        self.assertIn("[ERROR]", result)

    def test_write_no_message(self):
        result = _run(self.handler("write info"))
        self.assertIn("Usage", result)

    def test_write_invalid_level(self):
        result = _run(self.handler("write trace msg"))
        self.assertIn("Invalid level", result)

    def test_write_debug(self):
        result = _run(self.handler("write debug debug msg"))
        self.assertIn("[DEBUG]", result)

    # --- search ---

    def test_search_empty(self):
        result = _run(self.handler("search hello"))
        self.assertIn("No matching", result)

    def test_search_finds_records(self):
        _run(self.handler("write info test message"))
        result = _run(self.handler("search test"))
        self.assertIn("1 record", result)

    def test_search_no_text(self):
        _run(self.handler("write info msg"))
        result = _run(self.handler("search"))
        self.assertIn("1 record", result)

    # --- routes ---

    def test_routes_empty(self):
        result = _run(self.handler("routes"))
        self.assertIn("No routes", result)

    # --- rotate ---

    def test_rotate_empty(self):
        result = _run(self.handler("rotate"))
        self.assertIn("No records", result)

    def test_rotate_archives(self):
        _run(self.handler("write info one"))
        _run(self.handler("write warning two"))
        result = _run(self.handler("rotate"))
        self.assertIn("Rotated 2 record", result)

    def test_rotate_clears_records(self):
        _run(self.handler("write info one"))
        _run(self.handler("rotate"))
        result = _run(self.handler("stats"))
        self.assertIn("Total records: 0", result)

    # --- stats ---

    def test_stats_empty(self):
        result = _run(self.handler("stats"))
        self.assertIn("Total records: 0", result)
        self.assertIn("Archived: 0", result)

    def test_stats_with_records(self):
        _run(self.handler("write info x"))
        _run(self.handler("write error y"))
        result = _run(self.handler("stats"))
        self.assertIn("Total records: 2", result)
        self.assertIn('"info"', result)
        self.assertIn('"error"', result)

    def test_stats_after_rotate(self):
        _run(self.handler("write info x"))
        _run(self.handler("rotate"))
        result = _run(self.handler("stats"))
        self.assertIn("Archived: 1", result)


if __name__ == "__main__":
    unittest.main()
