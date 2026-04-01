"""Tests for CLI commands in q234_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q234_cmds import register
from lidco.cli.commands.registry import CommandRegistry, SlashCommand


def _make_registry() -> CommandRegistry:
    """Create a minimal registry and register Q234 commands."""

    class MiniRegistry:
        def __init__(self) -> None:
            self._commands: dict[str, SlashCommand] = {}

        def register(self, cmd: SlashCommand) -> None:
            self._commands[cmd.name] = cmd

        def get(self, name: str) -> SlashCommand | None:
            return self._commands.get(name)

    reg = MiniRegistry()  # type: ignore[assignment]
    register(reg)
    return reg  # type: ignore[return-value]


class TestQ234Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = _make_registry()

    def test_budget_history_registered(self) -> None:
        cmd = self.reg.get("budget-history")
        self.assertIsNotNone(cmd)

    def test_budget_history_no_args(self) -> None:
        cmd = self.reg.get("budget-history")
        result = asyncio.run(cmd.handler(""))  # type: ignore[union-attr]
        self.assertIn("No budget history", result)

    def test_efficiency_registered(self) -> None:
        cmd = self.reg.get("efficiency")
        self.assertIsNotNone(cmd)

    def test_efficiency_no_args(self) -> None:
        cmd = self.reg.get("efficiency")
        result = asyncio.run(cmd.handler(""))  # type: ignore[union-attr]
        self.assertIn("Usage", result)

    def test_efficiency_with_args(self) -> None:
        cmd = self.reg.get("efficiency")
        result = asyncio.run(cmd.handler("1000 800"))  # type: ignore[union-attr]
        self.assertIn("Grade:", result)

    def test_optimize_budget_registered(self) -> None:
        cmd = self.reg.get("optimize-budget")
        self.assertIsNotNone(cmd)

    def test_optimize_budget_no_args(self) -> None:
        cmd = self.reg.get("optimize-budget")
        result = asyncio.run(cmd.handler(""))  # type: ignore[union-attr]
        self.assertIn("Usage", result)

    def test_optimize_budget_with_args(self) -> None:
        cmd = self.reg.get("optimize-budget")
        result = asyncio.run(cmd.handler("100000 128000 0 25"))  # type: ignore[union-attr]
        self.assertIn("recommendations", result)

    def test_compare_budgets_registered(self) -> None:
        cmd = self.reg.get("compare-budgets")
        self.assertIsNotNone(cmd)

    def test_compare_budgets_no_args(self) -> None:
        cmd = self.reg.get("compare-budgets")
        result = asyncio.run(cmd.handler(""))  # type: ignore[union-attr]
        self.assertIn("Usage", result)

    def test_compare_budgets_with_args(self) -> None:
        cmd = self.reg.get("compare-budgets")
        result = asyncio.run(cmd.handler("A 1000 0.8 0.05 B 1000 0.6 0.03"))  # type: ignore[union-attr]
        self.assertIn("winner:", result)


if __name__ == "__main__":
    unittest.main()
