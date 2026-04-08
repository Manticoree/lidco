"""Tests for lidco.cli.commands.q321_cmds — CLI wiring."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q321_cmds import register_q321_commands


class _FakeRegistry:
    """Minimal registry stub collecting registered commands."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = (description, handler)


class TestRegisterQ321Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _FakeRegistry()
        register_q321_commands(self.registry)

    def test_all_commands_registered(self) -> None:
        expected = {"cloud-cost", "cost-forecast", "find-savings", "cost-dashboard"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    def test_descriptions_non_empty(self) -> None:
        for name, (desc, _) in self.registry.commands.items():
            self.assertTrue(desc, f"{name} has empty description")

    def test_handlers_are_callable(self) -> None:
        for name, (_, handler) in self.registry.commands.items():
            self.assertTrue(callable(handler), f"{name} handler not callable")


class TestCloudCostHandler(unittest.TestCase):
    def test_cloud_cost_empty(self) -> None:
        reg = _FakeRegistry()
        register_q321_commands(reg)
        handler = reg.commands["cloud-cost"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Cloud Cost", result)

    def test_cloud_cost_with_args(self) -> None:
        reg = _FakeRegistry()
        register_q321_commands(reg)
        handler = reg.commands["cloud-cost"][1]
        result = asyncio.run(handler("--start 2026-01-01 --end 2026-01-31"))
        self.assertIn("Cloud Cost", result)


class TestCostForecastHandler(unittest.TestCase):
    def test_forecast_empty(self) -> None:
        reg = _FakeRegistry()
        register_q321_commands(reg)
        handler = reg.commands["cost-forecast"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Cost Forecast", result)

    def test_forecast_with_budget(self) -> None:
        reg = _FakeRegistry()
        register_q321_commands(reg)
        handler = reg.commands["cost-forecast"][1]
        result = asyncio.run(handler("--budget 1000 --periods 5"))
        self.assertIn("Cost Forecast", result)


class TestFindSavingsHandler(unittest.TestCase):
    def test_find_savings_empty(self) -> None:
        reg = _FakeRegistry()
        register_q321_commands(reg)
        handler = reg.commands["find-savings"][1]
        result = asyncio.run(handler(""))
        self.assertIn("No savings opportunities", result)


class TestCostDashboardHandler(unittest.TestCase):
    def test_dashboard_empty(self) -> None:
        reg = _FakeRegistry()
        register_q321_commands(reg)
        handler = reg.commands["cost-dashboard"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Cost Dashboard", result)

    def test_dashboard_with_threshold(self) -> None:
        reg = _FakeRegistry()
        register_q321_commands(reg)
        handler = reg.commands["cost-dashboard"][1]
        result = asyncio.run(handler("--threshold 3.0"))
        self.assertIn("Cost Dashboard", result)


if __name__ == "__main__":
    unittest.main()
