"""Tests for lidco.cli.commands.q224_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.registry import CommandRegistry
from lidco.cli.commands.q224_cmds import register


def _run(coro):
    return asyncio.run(coro)


class TestQ224Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CommandRegistry()
        register(self.registry)

    def test_all_commands_registered(self) -> None:
        names = {"route", "model-stats", "quality-track", "cost-quality"}
        for name in names:
            self.assertIn(name, self.registry._commands, f"/{name} not registered")

    def test_route_no_args(self) -> None:
        handler = self.registry._commands["route"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_route_simple_prompt(self) -> None:
        handler = self.registry._commands["route"].handler
        result = _run(handler("Fix a typo"))
        self.assertIn("Complexity", result)
        self.assertIn("Model", result)

    def test_route_complex_prompt(self) -> None:
        handler = self.registry._commands["route"].handler
        result = _run(handler("Refactor the auth module then optimise performance"))
        self.assertIn("Complexity", result)

    def test_model_stats_empty(self) -> None:
        handler = self.registry._commands["model-stats"].handler
        result = _run(handler(""))
        self.assertIn("No quality records", result)

    def test_quality_track_no_args(self) -> None:
        handler = self.registry._commands["quality-track"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_quality_track_valid(self) -> None:
        handler = self.registry._commands["quality-track"].handler
        result = _run(handler("claude-sonnet-4 0.85"))
        self.assertIn("Recorded", result)
        self.assertIn("claude-sonnet-4", result)

    def test_quality_track_bad_score(self) -> None:
        handler = self.registry._commands["quality-track"].handler
        result = _run(handler("model abc"))
        self.assertIn("number", result)

    def test_cost_quality_empty(self) -> None:
        handler = self.registry._commands["cost-quality"].handler
        result = _run(handler(""))
        self.assertIn("No model profiles", result)


if __name__ == "__main__":
    unittest.main()
