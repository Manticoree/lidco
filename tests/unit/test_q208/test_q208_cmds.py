"""Tests for lidco.cli.commands.q208_cmds — /migrate, /bootstrap, /setup, /doctor."""

from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.registry import CommandRegistry
from lidco.cli.commands.q208_cmds import register, _state


class TestQ208Commands(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()
        self.registry = CommandRegistry()
        register(self.registry)

    def _run(self, name: str, args: str = "") -> str:
        cmd = self.registry._commands[name]
        return asyncio.run(cmd.handler(args))

    def test_migrate_help(self) -> None:
        result = self._run("migrate", "")
        assert "Usage" in result

    def test_migrate_status_empty(self) -> None:
        result = self._run("migrate", "status")
        assert "No migrations" in result

    def test_bootstrap_help(self) -> None:
        result = self._run("bootstrap", "")
        assert "Usage" in result

    def test_setup_test(self) -> None:
        result = self._run("setup", "test")
        assert "OK" in result

    def test_setup_api_key(self) -> None:
        result = self._run("setup", "api-key sk-test")
        assert "configured" in result

    def test_setup_model(self) -> None:
        result = self._run("setup", "model gpt-4")
        assert "gpt-4" in result

    def test_doctor(self) -> None:
        result = self._run("doctor", "")
        assert "System doctor" in result
        assert "not initialized" in result


if __name__ == "__main__":
    unittest.main()
