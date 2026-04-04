"""Tests for Q276 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest

from lidco.cli.commands.registry import CommandRegistry, SlashCommand
from lidco.cli.commands import q276_cmds


class TestQ276Commands(unittest.TestCase):
    def setUp(self):
        # Reset module state between tests
        q276_cmds._state.clear()
        self.registry = CommandRegistry()
        q276_cmds.register(self.registry)

    def _run(self, name: str, args: str) -> str:
        cmd = self.registry._commands[name]
        return asyncio.run(cmd.handler(args))

    # -- /preset -----------------------------------------------------------

    def test_preset_list_empty(self):
        result = self._run("preset", "list")
        self.assertIn("No templates", result)

    def test_preset_create_and_get(self):
        payload = json.dumps({"description": "Test template", "tools": ["read"]})
        result = self._run("preset", f"create mytest {payload}")
        self.assertIn("created", result)
        result = self._run("preset", "get mytest")
        self.assertIn("mytest", result)
        self.assertIn("Test template", result)

    def test_preset_remove(self):
        payload = json.dumps({"description": "tmp"})
        self._run("preset", f"create tmp {payload}")
        result = self._run("preset", "remove tmp")
        self.assertIn("removed", result)
        result = self._run("preset", "remove tmp")
        self.assertIn("not found", result)

    # -- /preset-library ---------------------------------------------------

    def test_preset_library_list(self):
        result = self._run("preset-library", "list")
        self.assertIn("bug-fix", result)
        self.assertIn("feature", result)

    def test_preset_library_builtin(self):
        result = self._run("preset-library", "builtin")
        self.assertIn("bug-fix", result)
        self.assertIn("docs", result)

    def test_preset_library_category(self):
        result = self._run("preset-library", "category development")
        self.assertIn("bug-fix", result)

    # -- /preset-compose ---------------------------------------------------

    def test_preset_compose_preview(self):
        result = self._run("preset-compose", "preview bug-fix")
        self.assertIn("bug-fix", result)
        self.assertIn("Category", result)

    def test_preset_compose_merge(self):
        result = self._run("preset-compose", "merge bug-fix review merged")
        self.assertIn("Merged", result)


if __name__ == "__main__":
    unittest.main()
