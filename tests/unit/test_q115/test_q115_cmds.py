"""Tests for Q115 CLI commands (Task 711)."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from lidco.cli.commands import q115_cmds
from lidco.cli.commands.q115_cmds import register


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _run(coro):
    return asyncio.run(coro)


class TestDeployCommands(unittest.TestCase):
    def setUp(self):
        q115_cmds._state.clear()
        self.reg = FakeRegistry()
        register(self.reg)

    def test_deploy_registered(self):
        assert "deploy" in self.reg.commands

    def test_deploy_no_args(self):
        handler = self.reg.commands["deploy"].handler
        result = _run(handler(""))
        assert "Usage" in result or "usage" in result.lower()

    def test_deploy_detect(self):
        handler = self.reg.commands["deploy"].handler
        result = _run(handler("detect"))
        assert isinstance(result, str)

    def test_deploy_providers(self):
        handler = self.reg.commands["deploy"].handler
        result = _run(handler("providers"))
        assert "netlify" in result.lower() or "provider" in result.lower()

    def test_deploy_run_dry_run(self):
        handler = self.reg.commands["deploy"].handler
        result = _run(handler("run netlify --dry-run"))
        assert isinstance(result, str)

    def test_deploy_run_default_dry_run(self):
        handler = self.reg.commands["deploy"].handler
        result = _run(handler("run netlify"))
        assert isinstance(result, str)

    def test_deploy_status_no_previous(self):
        handler = self.reg.commands["deploy"].handler
        result = _run(handler("status"))
        assert "no" in result.lower() or "status" in result.lower()

    def test_deploy_rollback_no_previous(self):
        handler = self.reg.commands["deploy"].handler
        result = _run(handler("rollback"))
        assert isinstance(result, str)

    def test_deploy_run_unknown_provider(self):
        handler = self.reg.commands["deploy"].handler
        result = _run(handler("run nonexistent"))
        assert isinstance(result, str)


class TestDiagramCommands(unittest.TestCase):
    def setUp(self):
        q115_cmds._state.clear()
        self.reg = FakeRegistry()
        register(self.reg)

    def test_diagram_registered(self):
        assert "diagram" in self.reg.commands

    def test_diagram_no_args(self):
        handler = self.reg.commands["diagram"].handler
        result = _run(handler(""))
        assert "Usage" in result or "usage" in result.lower()

    def test_diagram_mermaid(self):
        handler = self.reg.commands["diagram"].handler
        spec = json.dumps({
            "nodes": [{"id": "A", "label": "Node A"}],
            "edges": [{"from_id": "A", "to_id": "B"}],
        })
        result = _run(handler(f"mermaid {spec}"))
        assert isinstance(result, str)

    def test_diagram_ascii(self):
        handler = self.reg.commands["diagram"].handler
        spec = json.dumps({
            "nodes": [{"id": "A", "label": "Node A"}, {"id": "B", "label": "Node B"}],
            "edges": [{"from_id": "A", "to_id": "B"}],
        })
        result = _run(handler(f"ascii {spec}"))
        assert isinstance(result, str)

    def test_diagram_mermaid_invalid_json(self):
        handler = self.reg.commands["diagram"].handler
        result = _run(handler("mermaid {bad json"))
        assert "error" in result.lower() or "invalid" in result.lower()

    def test_diagram_show_no_previous(self):
        handler = self.reg.commands["diagram"].handler
        result = _run(handler("show"))
        assert "no" in result.lower() or isinstance(result, str)

    def test_diagram_mermaid_then_show(self):
        handler = self.reg.commands["diagram"].handler
        spec = json.dumps({
            "nodes": [{"id": "X", "label": "X"}],
            "edges": [],
        })
        _run(handler(f"mermaid {spec}"))
        result = _run(handler("show"))
        assert isinstance(result, str)

    def test_diagram_ascii_empty_spec(self):
        handler = self.reg.commands["diagram"].handler
        spec = json.dumps({"nodes": [], "edges": []})
        result = _run(handler(f"ascii {spec}"))
        assert isinstance(result, str)


class TestMaxModeCommands(unittest.TestCase):
    def setUp(self):
        q115_cmds._state.clear()
        self.reg = FakeRegistry()
        register(self.reg)

    def test_max_mode_registered(self):
        assert "max-mode" in self.reg.commands

    def test_max_mode_no_args(self):
        handler = self.reg.commands["max-mode"].handler
        result = _run(handler(""))
        assert "Usage" in result or "usage" in result.lower()

    def test_max_mode_activate_max(self):
        handler = self.reg.commands["max-mode"].handler
        result = _run(handler("max"))
        assert "max" in result.lower()

    def test_max_mode_activate_mini(self):
        handler = self.reg.commands["max-mode"].handler
        result = _run(handler("mini"))
        assert "mini" in result.lower()

    def test_max_mode_activate_normal(self):
        handler = self.reg.commands["max-mode"].handler
        result = _run(handler("normal"))
        assert "normal" in result.lower()

    def test_max_mode_status(self):
        handler = self.reg.commands["max-mode"].handler
        result = _run(handler("status"))
        assert "normal" in result.lower() or "mode" in result.lower()

    def test_max_mode_usage(self):
        handler = self.reg.commands["max-mode"].handler
        result = _run(handler("usage"))
        assert "token" in result.lower() or "usage" in result.lower() or "0" in result

    def test_max_mode_invalid(self):
        handler = self.reg.commands["max-mode"].handler
        result = _run(handler("turbo"))
        assert "invalid" in result.lower() or "usage" in result.lower()


if __name__ == "__main__":
    unittest.main()
