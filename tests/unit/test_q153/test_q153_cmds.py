"""Tests for Q153 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q153_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ153Commands(unittest.TestCase):
    def setUp(self):
        q153_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q153_cmds.register(MockRegistry())
        self.handler = self.registered["perf"].handler

    def test_command_registered(self):
        self.assertIn("perf", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    # --- time ---

    def test_time_start(self):
        result = _run(self.handler("time start myop"))
        self.assertIn("Timer started", result)
        self.assertIn("myop", result)

    def test_time_start_default_name(self):
        result = _run(self.handler("time start"))
        self.assertIn("unnamed", result)

    def test_time_stop_unknown(self):
        result = _run(self.handler("time stop bad_id"))
        self.assertIn("unknown", result.lower())

    def test_time_summary_empty(self):
        result = _run(self.handler("time summary"))
        self.assertIn("No timing", result)

    def test_time_slowest_empty(self):
        result = _run(self.handler("time slowest"))
        self.assertIn("No timing", result)

    def test_time_clear(self):
        result = _run(self.handler("time clear"))
        self.assertIn("cleared", result.lower())

    def test_time_no_action(self):
        result = _run(self.handler("time"))
        self.assertIn("Timing records:", result)

    # --- memory ---

    def test_memory_snapshot(self):
        result = _run(self.handler("memory snapshot test"))
        self.assertIn("Snapshot", result)
        self.assertIn("test", result)

    def test_memory_snapshot_default_label(self):
        result = _run(self.handler("memory snapshot"))
        self.assertIn("manual", result)

    def test_memory_peak_empty(self):
        result = _run(self.handler("memory peak"))
        self.assertIn("No snapshots", result)

    def test_memory_report_empty(self):
        result = _run(self.handler("memory report"))
        self.assertIn("No snapshots", result)

    def test_memory_clear(self):
        result = _run(self.handler("memory clear"))
        self.assertIn("cleared", result.lower())

    def test_memory_no_action(self):
        result = _run(self.handler("memory"))
        self.assertIn("Snapshots:", result)

    # --- bottleneck ---

    def test_bottleneck_analyze_empty(self):
        result = _run(self.handler("bottleneck analyze"))
        self.assertIn("No bottlenecks", result)

    def test_bottleneck_suggest_empty(self):
        result = _run(self.handler("bottleneck suggest"))
        self.assertIn("No suggestions", result)

    def test_bottleneck_no_action(self):
        result = _run(self.handler("bottleneck"))
        self.assertIn("Bottlenecks:", result)

    # --- report ---

    def test_report_summary(self):
        result = _run(self.handler("report summary"))
        self.assertIn("Performance Summary", result)

    def test_report_trend(self):
        result = _run(self.handler("report trend"))
        self.assertIn("Trend:", result)


if __name__ == "__main__":
    unittest.main()
