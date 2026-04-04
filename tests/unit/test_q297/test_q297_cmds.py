"""Tests for Q297 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q297_cmds import register, _state


class TestQ297Cmds(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.registry = MagicMock()
        self.handlers: dict[str, object] = {}

        def capture(cmd):
            self.handlers[cmd.name] = cmd.handler

        self.registry.register.side_effect = capture
        register(self.registry)

    def test_registered_commands(self):
        self.assertIn("metrics", self.handlers)
        self.assertIn("analyze-logs", self.handlers)
        self.assertIn("traces", self.handlers)
        self.assertIn("alerts", self.handlers)

    # -- /metrics ----------------------------------------------------------

    def test_metrics_help(self):
        result = asyncio.run(self.handlers["metrics"](""))
        self.assertIn("Usage", result)

    def test_metrics_counter(self):
        result = asyncio.run(self.handlers["metrics"]("counter req"))
        self.assertIn("req", result)
        self.assertIn("1", result)

    def test_metrics_record(self):
        result = asyncio.run(self.handlers["metrics"]("record cpu 0.75"))
        self.assertIn("Recorded", result)

    def test_metrics_export_json(self):
        asyncio.run(self.handlers["metrics"]("counter x"))
        result = asyncio.run(self.handlers["metrics"]("export json"))
        self.assertIn('"x"', result)

    def test_metrics_summary(self):
        result = asyncio.run(self.handlers["metrics"]("summary"))
        self.assertIn("total_points", result)

    # -- /analyze-logs -----------------------------------------------------

    def test_analyze_logs_help(self):
        result = asyncio.run(self.handlers["analyze-logs"](""))
        self.assertIn("Usage", result)

    def test_analyze_logs_ingest(self):
        result = asyncio.run(self.handlers["analyze-logs"]("ingest INFO hello\\nERROR fail"))
        self.assertIn("Ingested", result)

    def test_analyze_logs_root_cause(self):
        result = asyncio.run(self.handlers["analyze-logs"]("root-cause timeout error"))
        self.assertIn("timeout", result.lower())

    # -- /traces -----------------------------------------------------------

    def test_traces_help(self):
        result = asyncio.run(self.handlers["traces"](""))
        self.assertIn("Usage", result)

    def test_traces_start(self):
        result = asyncio.run(self.handlers["traces"]("start my_op"))
        self.assertIn("Started span", result)

    # -- /alerts -----------------------------------------------------------

    def test_alerts_help(self):
        result = asyncio.run(self.handlers["alerts"](""))
        self.assertIn("Usage", result)

    def test_alerts_add(self):
        result = asyncio.run(self.handlers["alerts"]("add cpu_high gt 90"))
        self.assertIn("Rule", result)
        self.assertIn("created", result)

    def test_alerts_active(self):
        asyncio.run(self.handlers["alerts"]("add x gt 0"))
        # Need to evaluate to fire
        result = asyncio.run(self.handlers["alerts"]("active"))
        self.assertIn("No active alerts", result)


if __name__ == "__main__":
    unittest.main()
