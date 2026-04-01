"""Tests for cli.commands.q227_cmds — /context-meter, /model-limits, /usage-dashboard, /budget-alerts."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class TestQ227Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q227_cmds

        q227_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"context-meter", "model-limits", "usage-dashboard", "budget-alerts"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_context_meter_default(self):
        handler = self.registered["context-meter"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Context:", result)

    def test_context_meter_with_limit(self):
        handler = self.registered["context-meter"].handler
        result = asyncio.run(handler("200000"))
        self.assertIn("200,000", result)

    def test_model_limits_all(self):
        handler = self.registered["model-limits"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Model Registry", result)

    def test_model_limits_specific(self):
        handler = self.registered["model-limits"].handler
        result = asyncio.run(handler("claude-opus-4"))
        self.assertIn("claude-opus-4", result)
        self.assertIn("200,000", result)

    def test_model_limits_unknown(self):
        handler = self.registered["model-limits"].handler
        result = asyncio.run(handler("nonexistent-xyz"))
        self.assertIn("Unknown", result)

    def test_usage_dashboard(self):
        handler = self.registered["usage-dashboard"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage Dashboard", result)

    def test_budget_alerts(self):
        handler = self.registered["budget-alerts"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Threshold Alerter", result)


if __name__ == "__main__":
    unittest.main()
