"""Tests for Q182 CLI commands."""

import asyncio
from unittest.mock import MagicMock

from lidco.cli.commands import q182_cmds


def _make_registry():
    reg = MagicMock()
    registered = {}

    def fake_register(cmd):
        registered[cmd.name] = cmd

    reg.register = fake_register
    q182_cmds._state.clear()
    q182_cmds.register(reg)
    return registered


class TestQ182Commands:
    def test_budget_handler_default(self):
        cmds = _make_registry()
        assert "budget" in cmds
        result = asyncio.run(cmds["budget"].handler(""))
        assert "No budgets" in result

    def test_cost_alerts_handler_default(self):
        cmds = _make_registry()
        assert "cost-alerts" in cmds
        result = asyncio.run(cmds["cost-alerts"].handler(""))
        assert "Total cost" in result

    def test_model_optimizer_handler_default(self):
        cmds = _make_registry()
        assert "model-optimizer" in cmds
        result = asyncio.run(cmds["model-optimizer"].handler(""))
        assert "Model tiers" in result

    def test_batch_stats_handler_default(self):
        cmds = _make_registry()
        assert "batch-stats" in cmds
        result = asyncio.run(cmds["batch-stats"].handler(""))
        assert "Requests: 0" in result

    def test_budget_list_subcommand(self):
        cmds = _make_registry()
        result = asyncio.run(cmds["budget"].handler("list"))
        assert "No budgets" in result

    def test_cost_alerts_rules_subcommand(self):
        cmds = _make_registry()
        result = asyncio.run(cmds["cost-alerts"].handler("rules"))
        assert "No alert rules" in result

    def test_model_optimizer_classify_subcommand(self):
        cmds = _make_registry()
        result = asyncio.run(cmds["model-optimizer"].handler("classify summarize this"))
        assert "simple" in result.lower()

    def test_model_optimizer_tiers_subcommand(self):
        cmds = _make_registry()
        result = asyncio.run(cmds["model-optimizer"].handler("tiers"))
        assert "No model tiers" in result
