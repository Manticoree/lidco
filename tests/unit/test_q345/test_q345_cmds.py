"""Tests for Q345 CLI commands (Q345)."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock


def _make_registry():
    """Return a minimal mock registry with register_slash_command tracking."""
    registry = MagicMock()
    registry._handlers = {}

    def register_slash_command(name, handler):
        registry._handlers[name] = handler

    registry.register_slash_command.side_effect = register_slash_command
    return registry


def _setup():
    from lidco.cli.commands.q345_cmds import register_q345_commands
    registry = _make_registry()
    register_q345_commands(registry)
    return registry


class TestRegistration(unittest.TestCase):
    def test_all_four_commands_registered(self):
        registry = _setup()
        self.assertIn("api-freeze", registry._handlers)
        self.assertIn("plugin-compat", registry._handlers)
        self.assertIn("config-schema", registry._handlers)
        self.assertIn("tool-integrity", registry._handlers)


class TestApiFreezeCommand(unittest.TestCase):
    def _call(self, args):
        registry = _setup()
        return asyncio.run(registry._handlers["api-freeze"](args))

    def test_help_flag_returns_usage(self):
        out = self._call("--help")
        self.assertIn("Usage", out)

    def test_empty_args_returns_usage(self):
        out = self._call("")
        self.assertIn("Usage", out)

    def test_demo_returns_changes(self):
        out = self._call("demo")
        # demo has breaking changes
        self.assertIn("change", out.lower())

    def test_invalid_json_returns_error(self):
        out = self._call("{not valid json}")
        self.assertIn("Error", out)

    def test_valid_json_no_changes(self):
        api = {"functions": [{"name": "fn", "params": ["x"], "return_type": "str"}]}
        payload = json.dumps({"old": api, "new": api})
        out = self._call(payload)
        self.assertIn("No breaking changes", out)


class TestPluginCompatCommand(unittest.TestCase):
    def _call(self, args):
        registry = _setup()
        return asyncio.run(registry._handlers["plugin-compat"](args))

    def test_help_returns_usage(self):
        out = self._call("--help")
        self.assertIn("Usage", out)

    def test_demo_runs_without_error(self):
        out = self._call("demo")
        self.assertIn("compatibility", out.lower())

    def test_compatible_apis(self):
        api = {"version": "1.0.0", "methods": ["init", "run"]}
        payload = json.dumps({"plugin": api, "host": api})
        out = self._call(payload)
        self.assertIn("COMPATIBLE", out)


class TestConfigSchemaCommand(unittest.TestCase):
    def _call(self, args):
        registry = _setup()
        return asyncio.run(registry._handlers["config-schema"](args))

    def test_help_returns_usage(self):
        out = self._call("--help")
        self.assertIn("Usage", out)

    def test_demo_runs(self):
        out = self._call("demo")
        # demo has an unknown key
        self.assertIsInstance(out, str)
        self.assertGreater(len(out), 0)

    def test_clean_config_passes(self):
        schema = {"fields": [{"name": "host", "type": "str", "required": True, "default": "lo"}]}
        config = {"host": "example.com"}
        payload = json.dumps({"config": config, "schema": schema})
        out = self._call(payload)
        self.assertIn("passed", out.lower())


class TestToolIntegrityCommand(unittest.TestCase):
    def _call(self, args):
        registry = _setup()
        return asyncio.run(registry._handlers["tool-integrity"](args))

    def test_help_returns_usage(self):
        out = self._call("--help")
        self.assertIn("Usage", out)

    def test_demo_runs(self):
        out = self._call("demo")
        self.assertIn("tool", out.lower())

    def test_complete_clean_registry(self):
        tools = [
            {"name": "read", "has_run": True, "has_description": True, "permissions": ["read"]}
        ]
        payload = json.dumps({"tools": tools})
        out = self._call(payload)
        self.assertIn("complete", out.lower())


if __name__ == "__main__":
    unittest.main()
