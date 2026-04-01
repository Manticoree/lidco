"""Tests for lidco.cli.commands.q230_cmds."""
from __future__ import annotations

import asyncio

import pytest


def _run(coro):
    return asyncio.run(coro)


class TestQ230Commands:
    def _get_registry(self):
        from lidco.cli.commands.registry import CommandRegistry
        return CommandRegistry()

    def test_collapse_registered(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("collapse")
        assert cmd is not None
        assert "collapse" in cmd.description.lower() or "Collapse" in cmd.description

    def test_collapse_handler(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("collapse")
        result = _run(cmd.handler(""))
        assert "Collapsed" in result

    def test_importance_registered(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("importance")
        assert cmd is not None

    def test_importance_handler(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("importance")
        result = _run(cmd.handler(""))
        assert "Scored" in result

    def test_evict_registered(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("evict")
        assert cmd is not None

    def test_evict_handler(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("evict")
        result = _run(cmd.handler(""))
        assert "Evicted" in result

    def test_token_debt_registered(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("token-debt")
        assert cmd is not None

    def test_token_debt_handler(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("token-debt")
        result = _run(cmd.handler("1000 overflow"))
        assert "1000" in result
