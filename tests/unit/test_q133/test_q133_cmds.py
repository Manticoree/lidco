"""Tests for Q133 CLI commands."""
from __future__ import annotations
import asyncio
import json
import unittest
from lidco.cli.commands import q133_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ133Commands(unittest.TestCase):
    def setUp(self):
        q133_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q133_cmds.register(MockRegistry())
        self.handler = self.registered["debug"].handler

    def test_command_registered(self):
        self.assertIn("debug", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    # --- trace ---

    def test_trace_summary_empty(self):
        result = _run(self.handler("trace summary"))
        self.assertIn("{}", result)

    def test_trace_clear(self):
        result = _run(self.handler("trace clear"))
        self.assertIn("cleared", result.lower())

    def test_trace_last_empty(self):
        result = _run(self.handler("trace last"))
        self.assertIn("No trace", result)

    def test_trace_no_sub(self):
        result = _run(self.handler("trace"))
        self.assertIn("Trace entries: 0", result)

    # --- inspect ---

    def test_inspect_capture(self):
        data = json.dumps({"key": "value"})
        result = _run(self.handler(f"inspect capture {data}"))
        self.assertIn("Captured", result)

    def test_inspect_list_empty(self):
        result = _run(self.handler("inspect list"))
        self.assertIn("Snapshots: 0", result)

    def test_inspect_list_after_capture(self):
        _run(self.handler(f'inspect capture {json.dumps({"x": 1})}'))
        result = _run(self.handler("inspect list"))
        self.assertIn("Snapshots: 1", result)

    def test_inspect_clear(self):
        _run(self.handler(f'inspect capture {json.dumps({"x": 1})}'))
        result = _run(self.handler("inspect clear"))
        self.assertIn("cleared", result.lower())

    def test_inspect_capture_invalid_json(self):
        result = _run(self.handler("inspect capture {bad}"))
        self.assertIn("Invalid JSON", result)

    def test_inspect_capture_missing_args(self):
        result = _run(self.handler("inspect capture"))
        self.assertIn("Usage", result)

    def test_inspect_no_sub(self):
        result = _run(self.handler("inspect"))
        self.assertIn("Usage", result)

    # --- errors ---

    def test_errors_summary_empty(self):
        result = _run(self.handler("errors summary"))
        self.assertIn("total_records", result)

    def test_errors_top(self):
        result = _run(self.handler("errors top"))
        self.assertIn("Top", result)

    def test_errors_top_n(self):
        result = _run(self.handler("errors top 3"))
        self.assertIn("Top 3", result)

    def test_errors_clear(self):
        result = _run(self.handler("errors clear"))
        self.assertIn("cleared", result.lower())

    def test_errors_no_sub(self):
        result = _run(self.handler("errors"))
        self.assertIn("total_records", result)

    # --- log ---

    def test_log_add(self):
        result = _run(self.handler("log add info hello world"))
        self.assertIn("Logged", result)
        self.assertIn("info", result.lower())

    def test_log_tail_empty(self):
        result = _run(self.handler("log tail"))
        self.assertIn("Last", result)

    def test_log_tail_n(self):
        result = _run(self.handler("log tail 5"))
        self.assertIn("Last", result)

    def test_log_clear(self):
        _run(self.handler("log add info test message"))
        result = _run(self.handler("log clear"))
        self.assertIn("cleared", result.lower())

    def test_log_no_sub(self):
        result = _run(self.handler("log"))
        self.assertIn("Log entries:", result)

    def test_command_description(self):
        self.assertIn("Q133", self.registered["debug"].description)


if __name__ == "__main__":
    unittest.main()
