"""Tests for Q175 CLI commands — /watch-files, /changes, /refresh-context, /conflicts."""
from __future__ import annotations

import asyncio
import unittest

from lidco.awareness.file_monitor import FileMonitor, MonitorConfig
from lidco.awareness.reconciler import ContextReconciler
from lidco.awareness.stale_guard import StaleEditGuard
from lidco.awareness.git_listener import GitEventListener
from lidco.cli.commands.q175_cmds import register_q175_commands


class FakeRegistry:
    def __init__(self):
        self.commands: dict = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ175Commands(unittest.TestCase):
    def setUp(self):
        self.registry = FakeRegistry()
        register_q175_commands(self.registry)

    def test_register_commands_count(self):
        self.assertEqual(len(self.registry.commands), 4)

    def test_register_watch_files(self):
        self.assertIn("watch-files", self.registry.commands)

    def test_register_changes(self):
        self.assertIn("changes", self.registry.commands)

    def test_register_refresh_context(self):
        self.assertIn("refresh-context", self.registry.commands)

    def test_register_conflicts(self):
        self.assertIn("conflicts", self.registry.commands)

    def test_watch_files_on(self):
        result = asyncio.run(self.registry.commands["watch-files"].handler("on"))
        self.assertIn("enabled", result)

    def test_watch_files_off(self):
        result = asyncio.run(self.registry.commands["watch-files"].handler("off"))
        self.assertIn("disabled", result)

    def test_watch_files_status(self):
        result = asyncio.run(self.registry.commands["watch-files"].handler("status"))
        self.assertIn("inactive", result)
        self.assertIn("Poll interval", result)

    def test_watch_files_no_args(self):
        result = asyncio.run(self.registry.commands["watch-files"].handler(""))
        self.assertIn("Usage", result)

    def test_changes_handler(self):
        result = asyncio.run(self.registry.commands["changes"].handler(""))
        self.assertIn("No external changes", result)

    def test_refresh_context_handler(self):
        result = asyncio.run(self.registry.commands["refresh-context"].handler(""))
        self.assertIn("refreshed", result)

    def test_conflicts_handler(self):
        result = asyncio.run(self.registry.commands["conflicts"].handler(""))
        self.assertIn("No file conflicts", result)


if __name__ == "__main__":
    unittest.main()
