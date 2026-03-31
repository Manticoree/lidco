"""Tests for Q178 CLI commands."""
import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.registry import CommandRegistry, SlashCommand
from lidco.cli.commands.q178_cmds import register_q178_commands


class TestQ178Commands(unittest.TestCase):
    def setUp(self):
        self.registry = CommandRegistry()
        register_q178_commands(self.registry)

    def test_recover_registered(self):
        self.assertIn("recover", self.registry._commands)

    def test_health_registered(self):
        self.assertIn("health", self.registry._commands)

    def test_retry_stats_registered(self):
        self.assertIn("retry-stats", self.registry._commands)

    def test_degrade_registered(self):
        self.assertIn("degrade", self.registry._commands)

    def test_recover_handler(self):
        handler = self.registry._commands["recover"].handler
        result = asyncio.run(handler(""))
        self.assertIn("clean", result.lower())

    def test_health_handler_no_subsystems(self):
        handler = self.registry._commands["health"].handler
        result = asyncio.run(handler(""))
        self.assertIn("No subsystems", result)

    def test_retry_stats_handler_empty(self):
        handler = self.registry._commands["retry-stats"].handler
        result = asyncio.run(handler(""))
        self.assertIn("No retry statistics", result)

    def test_degrade_handler_list(self):
        handler = self.registry._commands["degrade"].handler
        result = asyncio.run(handler("list"))
        self.assertIn("No subsystems", result)

    def test_degrade_handler_disable(self):
        handler = self.registry._commands["degrade"].handler
        result = asyncio.run(handler("disable myservice"))
        self.assertIn("disabled", result.lower())

    def test_degrade_handler_enable(self):
        handler = self.registry._commands["degrade"].handler
        result = asyncio.run(handler("enable myservice"))
        self.assertIn("enabled", result.lower())

    def test_degrade_handler_usage(self):
        handler = self.registry._commands["degrade"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_all_commands_are_slash_commands(self):
        for name in ["recover", "health", "retry-stats", "degrade"]:
            cmd = self.registry._commands[name]
            self.assertIsInstance(cmd, SlashCommand)

    def test_all_handlers_are_async(self):
        for name in ["recover", "health", "retry-stats", "degrade"]:
            handler = self.registry._commands[name].handler
            self.assertTrue(asyncio.iscoroutinefunction(handler))

    def test_command_descriptions(self):
        for name in ["recover", "health", "retry-stats", "degrade"]:
            cmd = self.registry._commands[name]
            self.assertTrue(len(cmd.description) > 0)


if __name__ == "__main__":
    unittest.main()
