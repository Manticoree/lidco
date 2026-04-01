"""Tests for lidco.cli.commands.q231_cmds."""
from __future__ import annotations

import asyncio

import pytest


def _run(coro):
    return asyncio.run(coro)


class TestQ231Commands:
    def _get_registry(self):
        from lidco.cli.commands.registry import CommandRegistry
        return CommandRegistry()

    def test_budget_status_registered(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("budget-status")
        assert cmd is not None
        assert "budget" in cmd.description.lower()

    def test_budget_status_handler(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("budget-status")
        result = _run(cmd.handler(""))
        assert "Context" in result

    def test_budget_report_registered(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("budget-report")
        assert cmd is not None

    def test_budget_report_handler(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("budget-report")
        result = _run(cmd.handler(""))
        assert "Budget Report" in result

    def test_budget_config_registered(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("budget-config")
        assert cmd is not None

    def test_budget_config_handler(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("budget-config")
        result = _run(cmd.handler(""))
        assert "BudgetConfig" in result

    def test_budget_reset_registered(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("budget-reset")
        assert cmd is not None

    def test_budget_reset_handler(self) -> None:
        reg = self._get_registry()
        cmd = reg.get("budget-reset")
        result = _run(cmd.handler(""))
        assert "128,000" in result
