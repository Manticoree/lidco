"""Tests for lidco.cli.commands.q266_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

import lidco.cli.commands.q266_cmds as mod


class TestQ266Cmds(unittest.TestCase):
    def setUp(self) -> None:
        mod._state.clear()
        self.registry = MagicMock()
        mod.register(self.registry)
        self.cmds = {
            call.args[0].name: call.args[0].handler
            for call in self.registry.register.call_args_list
        }

    def test_registered_commands(self) -> None:
        self.assertIn("fleet", self.cmds)
        self.assertIn("distribute-config", self.cmds)
        self.assertIn("aggregate-usage", self.cmds)
        self.assertIn("enterprise-dashboard", self.cmds)

    def test_fleet_list_empty(self) -> None:
        result = asyncio.run(self.cmds["fleet"]("list"))
        self.assertIn("No instances", result)

    def test_fleet_register(self) -> None:
        result = asyncio.run(self.cmds["fleet"]("register web-1 2.0"))
        self.assertIn("Registered", result)
        self.assertIn("web-1", result)

    def test_fleet_health(self) -> None:
        result = asyncio.run(self.cmds["fleet"]("health"))
        self.assertIn("healthy", result)

    def test_distribute_config_publish(self) -> None:
        result = asyncio.run(self.cmds["distribute-config"]('publish {"key": "val"}'))
        self.assertIn("Published config version 1", result)

    def test_distribute_config_versions(self) -> None:
        asyncio.run(self.cmds["distribute-config"]('publish {"a": 1}'))
        result = asyncio.run(self.cmds["distribute-config"]("versions"))
        self.assertIn("v1", result)

    def test_aggregate_usage_total(self) -> None:
        result = asyncio.run(self.cmds["aggregate-usage"]("total"))
        self.assertIn("tokens", result)

    def test_enterprise_dashboard_default(self) -> None:
        result = asyncio.run(self.cmds["enterprise-dashboard"](""))
        self.assertIn("Enterprise Dashboard", result)


if __name__ == "__main__":
    unittest.main()
