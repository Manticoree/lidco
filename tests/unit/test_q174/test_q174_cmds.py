"""Tests for Q174 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.registry import SlashCommand


class MockRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}

    def register(self, cmd: SlashCommand) -> None:
        self._commands[cmd.name] = cmd

    def get(self, name: str) -> SlashCommand | None:
        return self._commands.get(name)

    def list_commands(self) -> list[SlashCommand]:
        return list(self._commands.values())


class TestQ174Commands(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q174_cmds import register_q174_commands
        self.registry = MockRegistry()
        register_q174_commands(self.registry)

    def test_register_commands_count(self) -> None:
        self.assertEqual(len(self.registry.list_commands()), 4)

    def test_explore_registered(self) -> None:
        cmd = self.registry.get("explore")
        self.assertIsNotNone(cmd)
        self.assertIn("exploration", cmd.description.lower())

    def test_explore_status_registered(self) -> None:
        cmd = self.registry.get("explore-status")
        self.assertIsNotNone(cmd)

    def test_explore_pick_registered(self) -> None:
        cmd = self.registry.get("explore-pick")
        self.assertIsNotNone(cmd)

    def test_explore_diff_registered(self) -> None:
        cmd = self.registry.get("explore-diff")
        self.assertIsNotNone(cmd)

    def test_explore_no_args(self) -> None:
        cmd = self.registry.get("explore")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_explore_with_prompt(self) -> None:
        cmd = self.registry.get("explore")
        result = asyncio.run(cmd.handler("fix the bug"))
        self.assertIn("Exploration", result)
        self.assertIn("created", result)
        self.assertIn("3 variants", result)

    def test_explore_with_variants_flag(self) -> None:
        cmd = self.registry.get("explore")
        result = asyncio.run(cmd.handler("fix bug --variants 2"))
        self.assertIn("2 variants", result)

    def test_explore_status_empty(self) -> None:
        # Use a fresh registry to get fresh spawner
        from lidco.cli.commands.q174_cmds import register_q174_commands
        reg = MockRegistry()
        register_q174_commands(reg)
        cmd = reg.get("explore-status")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("No active", result)

    def test_explore_status_after_create(self) -> None:
        cmd_explore = self.registry.get("explore")
        asyncio.run(cmd_explore.handler("do something"))
        cmd_status = self.registry.get("explore-status")
        result = asyncio.run(cmd_status.handler(""))
        self.assertIn("Explorations", result)

    def test_explore_pick_no_args(self) -> None:
        cmd = self.registry.get("explore-pick")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_explore_pick_with_id(self) -> None:
        cmd = self.registry.get("explore-pick")
        result = asyncio.run(cmd.handler("var_abc123"))
        self.assertIn("Selected variant", result)
        self.assertIn("var_abc123", result)

    def test_explore_diff_no_args(self) -> None:
        cmd = self.registry.get("explore-diff")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_explore_diff_with_ids(self) -> None:
        cmd = self.registry.get("explore-diff")
        result = asyncio.run(cmd.handler("v1 v2"))
        self.assertIn("Variant v1", result)
        self.assertIn("Variant v2", result)


if __name__ == "__main__":
    unittest.main()
