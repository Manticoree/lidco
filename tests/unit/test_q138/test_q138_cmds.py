"""Tests for Q138 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest

from lidco.cli.commands import q138_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ138Commands(unittest.TestCase):
    def setUp(self):
        q138_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q138_cmds.register(MockRegistry())
        self.handler = self.registered["resilience"].handler

    def test_command_registered(self):
        self.assertIn("resilience", self.registered)

    def test_command_description(self):
        self.assertIn("Q138", self.registered["resilience"].description)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    # --- retry ---

    def test_retry_stats(self):
        result = _run(self.handler("retry stats"))
        data = json.loads(result)
        self.assertIn("total_executions", data)

    def test_retry_reset(self):
        result = _run(self.handler("retry reset"))
        self.assertIn("reset", result.lower())

    def test_retry_test(self):
        result = _run(self.handler("retry test"))
        self.assertIn("success=True", result)
        self.assertIn("attempts=3", result)

    def test_retry_config(self):
        result = _run(self.handler("retry config"))
        self.assertIn("max_retries=3", result)
        self.assertIn("base_delay=", result)

    def test_retry_no_sub(self):
        result = _run(self.handler("retry"))
        data = json.loads(result)
        self.assertIn("total_executions", data)

    # --- fallback ---

    def test_fallback_count(self):
        result = _run(self.handler("fallback count"))
        self.assertIn("length:", result.lower())

    def test_fallback_clear(self):
        result = _run(self.handler("fallback clear"))
        self.assertIn("cleared", result.lower())

    def test_fallback_test(self):
        result = _run(self.handler("fallback test"))
        self.assertIn("fallback-ok", result)
        self.assertIn("fallback_used=True", result)

    def test_fallback_no_sub(self):
        result = _run(self.handler("fallback"))
        self.assertIn("length:", result.lower())

    # --- collect ---

    def test_collect_test(self):
        result = _run(self.handler("collect test"))
        self.assertIn("succeeded=1", result)
        self.assertIn("failed=1", result)
        self.assertIn("partial=True", result)

    def test_collect_rate(self):
        result = _run(self.handler("collect rate"))
        self.assertIn("rate", result.lower())

    def test_collect_no_sub(self):
        result = _run(self.handler("collect"))
        self.assertIn("rate", result.lower())

    # --- boundary ---

    def test_boundary_test(self):
        result = _run(self.handler("boundary test"))
        self.assertIn("Errors caught: 1", result)

    def test_boundary_log_empty(self):
        result = _run(self.handler("boundary log"))
        self.assertIn("No errors", result)

    def test_boundary_log_after_test(self):
        _run(self.handler("boundary test"))
        result = _run(self.handler("boundary log"))
        self.assertIn("Error log", result)
        self.assertIn("RuntimeError", result)

    def test_boundary_clear(self):
        _run(self.handler("boundary test"))
        result = _run(self.handler("boundary clear"))
        self.assertIn("cleared", result.lower())

    def test_boundary_count(self):
        result = _run(self.handler("boundary count"))
        self.assertIn("Errors caught:", result)

    def test_boundary_no_sub(self):
        result = _run(self.handler("boundary"))
        self.assertIn("Errors caught:", result)


if __name__ == "__main__":
    unittest.main()
