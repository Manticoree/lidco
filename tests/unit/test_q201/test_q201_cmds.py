"""Tests for lidco.cli.commands.q201_cmds."""

from __future__ import annotations

import asyncio

import pytest

from lidco.cli.commands.registry import CommandRegistry
from lidco.cli.commands import q201_cmds


@pytest.fixture(autouse=True)
def _clear_state():
    q201_cmds._state.clear()
    yield
    q201_cmds._state.clear()


@pytest.fixture
def registry() -> CommandRegistry:
    reg = CommandRegistry()
    q201_cmds.register(reg)
    return reg


def _run(coro):
    return asyncio.run(coro)


class TestQ201Commands:
    def test_cron_create(self, registry: CommandRegistry) -> None:
        cmd = registry._commands["cron-create"]
        result = _run(cmd.handler("*/5 * * * * my-job"))
        assert "Created job" in result
        assert "my-job" in result

    def test_cron_list_empty(self, registry: CommandRegistry) -> None:
        cmd = registry._commands["cron-list"]
        result = _run(cmd.handler(""))
        assert "No scheduled jobs" in result

    def test_cron_create_and_list(self, registry: CommandRegistry) -> None:
        create = registry._commands["cron-create"]
        _run(create.handler("0 * * * * hourly-task"))
        lst = registry._commands["cron-list"]
        result = _run(lst.handler(""))
        assert "hourly-task" in result
        assert "1 job(s)" in result

    def test_cron_delete_not_found(self, registry: CommandRegistry) -> None:
        cmd = registry._commands["cron-delete"]
        result = _run(cmd.handler("nonexistent"))
        assert "not found" in result

    def test_cron_create_invalid(self, registry: CommandRegistry) -> None:
        cmd = registry._commands["cron-create"]
        result = _run(cmd.handler("bad"))
        assert "Usage" in result
