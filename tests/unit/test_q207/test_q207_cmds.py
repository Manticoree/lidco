"""Tests for lidco.cli.commands.q207_cmds."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from lidco.cli.commands.registry import SlashCommand
from lidco.cli.commands.q207_cmds import register


def _run(coro):
    return asyncio.run(coro)


class _SimpleRegistry:
    """Minimal registry that collects commands without loading builtins."""

    def __init__(self):
        self._commands: dict[str, SlashCommand] = {}

    def register(self, cmd: SlashCommand) -> None:
        self._commands[cmd.name] = cmd


def _registry() -> _SimpleRegistry:
    reg = _SimpleRegistry()
    register(reg)
    return reg


def test_oauth_login_usage():
    reg = _registry()
    cmd = reg._commands["oauth-login"]
    result = _run(cmd.handler(""))
    assert "Usage" in result


def test_tokens_list():
    reg = _registry()
    cmd = reg._commands["tokens"]
    result = _run(cmd.handler("list"))
    assert "No tokens" in result


def test_keychain_clear():
    reg = _registry()
    cmd = reg._commands["keychain"]
    result = _run(cmd.handler("clear"))
    assert "Cleared" in result


def test_mcp_auth_summary():
    reg = _registry()
    cmd = reg._commands["mcp-auth"]
    result = _run(cmd.handler("summary"))
    assert "No MCP credentials" in result
