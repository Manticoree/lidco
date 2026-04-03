"""Tests for lidco.cli.commands.q270_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q270_cmds import register


class _FakeRegistry:
    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ270Commands(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register(self.registry)

    def test_all_commands_registered(self):
        self.assertIn("notify", self.registry.commands)
        self.assertIn("sound", self.registry.commands)
        self.assertIn("notify-rules", self.registry.commands)
        self.assertIn("notify-history", self.registry.commands)

    def test_notify_send(self):
        cmd = self.registry.commands["notify"]
        result = asyncio.run(cmd.handler("send Test Hello"))
        self.assertIn("Notification sent", result)

    def test_notify_enable(self):
        cmd = self.registry.commands["notify"]
        result = asyncio.run(cmd.handler("enable"))
        self.assertIn("enabled", result)

    def test_notify_usage(self):
        cmd = self.registry.commands["notify"]
        result = asyncio.run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_sound_play(self):
        cmd = self.registry.commands["sound"]
        result = asyncio.run(cmd.handler("play completion"))
        self.assertIn("Played sound", result)

    def test_sound_list(self):
        cmd = self.registry.commands["sound"]
        result = asyncio.run(cmd.handler("list"))
        self.assertIn("completion", result)

    def test_notify_rules_list(self):
        cmd = self.registry.commands["notify-rules"]
        result = asyncio.run(cmd.handler("list"))
        self.assertIn("default_completion", result)

    def test_notify_history_clear(self):
        cmd = self.registry.commands["notify-history"]
        result = asyncio.run(cmd.handler("clear"))
        self.assertIn("Cleared", result)


if __name__ == "__main__":
    unittest.main()
