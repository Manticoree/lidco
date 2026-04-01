"""Tests for Q203 CLI commands."""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

import lidco.cli.commands.q203_cmds as q203_mod


def _make_registry():
    """Create a minimal CommandRegistry and register Q203 commands."""
    from lidco.cli.commands.registry import CommandRegistry
    cr = CommandRegistry.__new__(CommandRegistry)
    cr._commands = {}
    cr._session = None
    q203_mod._state.clear()
    q203_mod.register(cr)
    return cr


class TestManagedSettingsCmd(unittest.TestCase):
    def setUp(self):
        self.cr = _make_registry()
        self.handler = self.cr._commands["managed-settings"].handler

    def test_help(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_load_file(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "test.json"
        p.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")
        result = asyncio.run(self.handler(f"load {p}"))
        self.assertIn("2 top-level keys", result)

    def test_load_missing(self):
        result = asyncio.run(self.handler("load /nonexistent/path.json"))
        self.assertIn("Error", result)


class TestPolicyCmd(unittest.TestCase):
    def setUp(self):
        self.cr = _make_registry()
        self.handler = self.cr._commands["policy"].handler

    def test_help(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_list_empty(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("No policies", result)


class TestSettingsHierarchyCmd(unittest.TestCase):
    def setUp(self):
        self.cr = _make_registry()
        self.handler = self.cr._commands["settings-hierarchy"].handler

    def test_help(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_layers_empty(self):
        result = asyncio.run(self.handler("layers"))
        self.assertIn("No layers", result)


class TestAdminCmd(unittest.TestCase):
    def setUp(self):
        self.cr = _make_registry()
        self.handler = self.cr._commands["admin"].handler

    def test_help(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_disable_plugin(self):
        result = asyncio.run(self.handler("disable-plugin test-plug security"))
        self.assertIn("Disabled", result)
        result2 = asyncio.run(self.handler("disabled-plugins"))
        self.assertIn("test-plug", result2)

    def test_audit_empty(self):
        q203_mod._state.clear()
        cr2 = _make_registry()
        handler2 = cr2._commands["admin"].handler
        result = asyncio.run(handler2("audit"))
        self.assertIn("No admin actions", result)


if __name__ == "__main__":
    unittest.main()
