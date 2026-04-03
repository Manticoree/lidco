"""Tests for Q265 CLI commands."""
from __future__ import annotations

import asyncio
import unittest


class _FakeRegistry:
    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_command(self, name: str, description: str, handler) -> None:
        self.commands[name] = (description, handler)


class TestQ265Commands(unittest.TestCase):
    def _registry(self) -> _FakeRegistry:
        from lidco.cli.commands.q265_cmds import register_q265_commands

        reg = _FakeRegistry()
        register_q265_commands(reg)
        return reg

    def test_all_commands_registered(self):
        reg = self._registry()
        assert "sso-login" in reg.commands
        assert "identity" in reg.commands
        assert "token" in reg.commands
        assert "user-directory" in reg.commands

    def test_sso_login_no_args(self):
        reg = self._registry()
        _, handler = reg.commands["sso-login"]
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_sso_login_config(self):
        reg = self._registry()
        _, handler = reg.commands["sso-login"]
        result = asyncio.run(handler("config okta https://okta.example.com cid"))
        assert "configured" in result.lower()

    def test_sso_login_login(self):
        reg = self._registry()
        _, handler = reg.commands["sso-login"]
        result = asyncio.run(handler("login"))
        assert "URL" in result

    def test_identity_no_args(self):
        reg = self._registry()
        _, handler = reg.commands["identity"]
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_token_no_args(self):
        reg = self._registry()
        _, handler = reg.commands["token"]
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_user_directory_no_args(self):
        reg = self._registry()
        _, handler = reg.commands["user-directory"]
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_user_directory_add(self):
        reg = self._registry()
        _, handler = reg.commands["user-directory"]
        result = asyncio.run(handler("add testuser"))
        assert "added" in result.lower()


if __name__ == "__main__":
    unittest.main()
