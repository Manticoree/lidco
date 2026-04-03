"""Tests for lidco.cli.commands.q226_cmds."""
from __future__ import annotations

import asyncio

import pytest


def _run(coro):
    return asyncio.run(coro)


class TestGatewayCommand:
    def test_no_args(self) -> None:
        from lidco.cli.commands.q226_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("gateway")
        assert cmd is not None
        result = _run(cmd.handler(""))
        assert "Usage" in result

    def test_add(self) -> None:
        from lidco.cli.commands.q226_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("gateway")
        result = _run(cmd.handler("add ep1 http://ep1.com"))
        assert "Added" in result


class TestApiKeysCommand:
    def test_no_args(self) -> None:
        from lidco.cli.commands.q226_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("api-keys")
        assert cmd is not None
        result = _run(cmd.handler(""))
        assert "Usage" in result

    def test_add(self) -> None:
        from lidco.cli.commands.q226_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("api-keys")
        result = _run(cmd.handler("add openai sk-test123"))
        assert "Added" in result


class TestApiUsageCommand:
    def test_no_args(self) -> None:
        from lidco.cli.commands.q226_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("api-usage")
        assert cmd is not None
        result = _run(cmd.handler(""))
        assert "Usage" in result

    def test_daily(self) -> None:
        from lidco.cli.commands.q226_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("api-usage")
        result = _run(cmd.handler("daily"))
        assert "{}" in result


class TestApiQueueCommand:
    def test_no_args(self) -> None:
        from lidco.cli.commands.q226_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("api-queue")
        assert cmd is not None
        result = _run(cmd.handler(""))
        assert "Usage" in result

    def test_enqueue(self) -> None:
        from lidco.cli.commands.q226_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("api-queue")
        result = _run(cmd.handler("enqueue openai test-payload"))
        assert "Enqueued" in result
