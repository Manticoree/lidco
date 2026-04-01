"""Tests for Q202 CLI commands."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from lidco.cli.commands.q202_cmds import _state, register
from lidco.cli.commands.registry import SlashCommand


class _SimpleRegistry:
    """Lightweight stand-in that only captures register() calls."""

    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}

    def register(self, cmd: SlashCommand) -> None:
        self._commands[cmd.name] = cmd


def _fresh_registry() -> _SimpleRegistry:
    _state.clear()
    reg = _SimpleRegistry()
    register(reg)
    return reg


class TestTeamCreateCmd:
    def test_create_no_args(self) -> None:
        reg = _fresh_registry()
        cmd = reg._commands["team-create"]
        result = asyncio.run(cmd.handler(""))
        assert "Usage" in result

    def test_create_success(self) -> None:
        reg = _fresh_registry()
        cmd = reg._commands["team-create"]
        result = asyncio.run(cmd.handler("myteam Some description"))
        assert "Created team" in result
        assert "myteam" in result


class TestTeamInviteCmd:
    def test_invite_no_args(self) -> None:
        reg = _fresh_registry()
        cmd = reg._commands["team-invite"]
        result = asyncio.run(cmd.handler(""))
        assert "Usage" in result


class TestTeamStatsCmd:
    def test_stats_no_args(self) -> None:
        reg = _fresh_registry()
        cmd = reg._commands["team-stats"]
        result = asyncio.run(cmd.handler(""))
        assert "Usage" in result

    def test_stats_empty(self) -> None:
        reg = _fresh_registry()
        cmd = reg._commands["team-stats"]
        result = asyncio.run(cmd.handler("t1"))
        assert "Total records: 0" in result
