"""Tests for cli.commands.q229_cmds — /task-score, /budget-scale, /estimate-cost, /budget-forecast."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class TestQ229Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q229_cmds

        q229_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"task-score", "budget-scale", "estimate-cost", "budget-forecast"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_task_score_usage(self):
        handler = self.registered["task-score"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_task_score_with_prompt(self):
        handler = self.registered["task-score"].handler
        result = asyncio.run(handler("refactor the entire module"))
        self.assertIn("TaskScore:", result)
        self.assertIn("Complexity:", result)

    def test_budget_scale_usage(self):
        handler = self.registered["budget-scale"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_budget_scale_with_score(self):
        handler = self.registered["budget-scale"].handler
        result = asyncio.run(handler("0.5 4096"))
        self.assertIn("Scale:", result)
        self.assertIn("->", result)

    def test_estimate_cost_usage(self):
        handler = self.registered["estimate-cost"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_estimate_cost_with_tool(self):
        handler = self.registered["estimate-cost"].handler
        result = asyncio.run(handler("Bash 50000"))
        self.assertIn("Estimate:", result)
        self.assertIn("Bash", result)

    def test_budget_forecast_default(self):
        handler = self.registered["budget-forecast"].handler
        result = asyncio.run(handler(""))
        self.assertIn("BudgetForecast", result)


if __name__ == "__main__":
    unittest.main()
