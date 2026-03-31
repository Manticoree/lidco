"""Tests for Q139 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q139_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ139Commands(unittest.TestCase):
    def setUp(self):
        q139_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q139_cmds.register(MockRegistry())
        self.handler = self.registered["ui"].handler

    def test_command_registered(self):
        self.assertIn("ui", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    # --- progress ---

    def test_progress_demo(self):
        result = _run(self.handler("progress demo"))
        self.assertIn("Demo", result)
        self.assertIn("%", result)

    def test_progress_create(self):
        result = _run(self.handler("progress create 50 Build"))
        self.assertIn("total=50", result)
        self.assertIn("Build", result)

    def test_progress_create_no_total(self):
        result = _run(self.handler("progress create"))
        self.assertIn("Usage", result)

    def test_progress_advance(self):
        _run(self.handler("progress create 10"))
        result = _run(self.handler("progress advance"))
        self.assertIn("%", result)

    def test_progress_advance_no_bar(self):
        result = _run(self.handler("progress advance"))
        self.assertIn("No active", result)

    def test_progress_finish(self):
        _run(self.handler("progress create 10"))
        result = _run(self.handler("progress finish"))
        self.assertIn("100%", result)

    def test_progress_finish_no_bar(self):
        result = _run(self.handler("progress finish"))
        self.assertIn("No active", result)

    def test_progress_show(self):
        _run(self.handler("progress create 10"))
        result = _run(self.handler("progress show"))
        self.assertIn("%", result)

    def test_progress_show_no_bar(self):
        result = _run(self.handler("progress show"))
        self.assertIn("No active", result)

    def test_progress_unknown(self):
        result = _run(self.handler("progress zzz"))
        self.assertIn("Usage", result)

    # --- table ---

    def test_table_demo(self):
        result = _run(self.handler("table demo"))
        self.assertIn("alpha", result)
        self.assertIn("+", result)

    def test_table_markdown(self):
        result = _run(self.handler("table markdown"))
        self.assertIn("|", result)
        self.assertIn("---", result)

    def test_table_compact(self):
        result = _run(self.handler("table compact"))
        self.assertIn("alpha", result)
        self.assertNotIn("+", result)

    def test_table_unknown(self):
        result = _run(self.handler("table zzz"))
        self.assertIn("Usage", result)

    # --- status ---

    def test_status_demo(self):
        result = _run(self.handler("status demo"))
        self.assertIn("Build", result)

    def test_status_duration(self):
        result = _run(self.handler("status duration 90"))
        self.assertIn("1m", result)

    def test_status_bytes(self):
        result = _run(self.handler("status bytes 2048"))
        self.assertIn("KB", result)

    def test_status_unknown(self):
        result = _run(self.handler("status zzz"))
        self.assertIn("Usage", result)

    # --- report ---

    def test_report_demo(self):
        result = _run(self.handler("report demo"))
        self.assertIn("Demo Report", result)
        self.assertIn("Overview", result)

    def test_report_markdown(self):
        result = _run(self.handler("report markdown"))
        self.assertIn("# Demo Report", result)

    def test_report_summary(self):
        result = _run(self.handler("report summary"))
        self.assertIn("Quick Report", result)
        self.assertIn("2 sections", result)

    def test_report_unknown(self):
        result = _run(self.handler("report zzz"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
