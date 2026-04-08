"""Tests for lidco.cli.commands.q322_cmds — CLI handlers."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class _FakeRegistry:
    """Minimal registry that records register_async calls."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler: object) -> None:
        self.commands[name] = (desc, handler)


class TestQ322Commands(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q322_cmds import register_q322_commands

        self.registry = _FakeRegistry()
        register_q322_commands(self.registry)

    def test_all_commands_registered(self) -> None:
        expected = {"deploy-blue-green", "deploy-canary", "deploy-rolling", "feature-deploy"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    # -- /deploy-blue-green -------------------------------------------------

    def test_blue_green_usage(self) -> None:
        handler = self.registry.commands["deploy-blue-green"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_blue_green_deploy(self) -> None:
        handler = self.registry.commands["deploy-blue-green"][1]
        result = asyncio.run(handler("v1.0"))
        self.assertIn("live", result.lower())
        self.assertIn("v1.0", result)

    def test_blue_green_status(self) -> None:
        handler = self.registry.commands["deploy-blue-green"][1]
        result = asyncio.run(handler("--status"))
        self.assertIn("Blue-Green Status", result)

    def test_blue_green_rollback(self) -> None:
        handler = self.registry.commands["deploy-blue-green"][1]
        result = asyncio.run(handler("--rollback"))
        self.assertIn("Rollback", result)

    # -- /deploy-canary -----------------------------------------------------

    def test_canary_usage(self) -> None:
        handler = self.registry.commands["deploy-canary"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_canary_deploy(self) -> None:
        handler = self.registry.commands["deploy-canary"][1]
        result = asyncio.run(handler("v2.0"))
        self.assertIn("promoted", result.lower())
        self.assertIn("v2.0", result)

    def test_canary_status(self) -> None:
        handler = self.registry.commands["deploy-canary"][1]
        result = asyncio.run(handler("--status"))
        self.assertIn("Canary Status", result)

    def test_canary_rollback_none(self) -> None:
        handler = self.registry.commands["deploy-canary"][1]
        result = asyncio.run(handler("--rollback"))
        self.assertIn("No active canary", result)

    def test_canary_custom_steps(self) -> None:
        handler = self.registry.commands["deploy-canary"][1]
        result = asyncio.run(handler("v3 --steps 10,50,100"))
        self.assertIn("promoted", result.lower())

    # -- /deploy-rolling ----------------------------------------------------

    def test_rolling_usage(self) -> None:
        handler = self.registry.commands["deploy-rolling"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_rolling_deploy(self) -> None:
        handler = self.registry.commands["deploy-rolling"][1]
        result = asyncio.run(handler("v1.0"))
        self.assertIn("completed", result.lower())

    def test_rolling_with_instances(self) -> None:
        handler = self.registry.commands["deploy-rolling"][1]
        result = asyncio.run(handler("v1 --instances a,b,c --batch-size 2"))
        self.assertIn("completed", result.lower())
        self.assertIn("3", result)  # 3 instances

    def test_rolling_status(self) -> None:
        handler = self.registry.commands["deploy-rolling"][1]
        result = asyncio.run(handler("--status"))
        self.assertIn("Rolling Status", result)

    # -- /feature-deploy ----------------------------------------------------

    def test_feature_deploy_usage(self) -> None:
        handler = self.registry.commands["feature-deploy"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_feature_deploy_create(self) -> None:
        handler = self.registry.commands["feature-deploy"][1]
        result = asyncio.run(handler("dark-mode"))
        self.assertIn("dark-mode", result)
        self.assertIn("created", result.lower())

    def test_feature_deploy_rollout(self) -> None:
        handler = self.registry.commands["feature-deploy"][1]
        result = asyncio.run(handler("new-ui --rollout"))
        self.assertIn("rollout started", result)

    def test_feature_deploy_kill(self) -> None:
        handler = self.registry.commands["feature-deploy"][1]
        result = asyncio.run(handler("new-ui --kill"))
        self.assertIn("KILLED", result)

    def test_feature_deploy_enable(self) -> None:
        handler = self.registry.commands["feature-deploy"][1]
        result = asyncio.run(handler("new-ui --enable"))
        self.assertIn("ENABLED", result)

    def test_feature_deploy_target(self) -> None:
        handler = self.registry.commands["feature-deploy"][1]
        result = asyncio.run(handler("new-ui --target alice,bob"))
        self.assertIn("targeted", result)
        self.assertIn("2", result)

    def test_feature_deploy_status(self) -> None:
        handler = self.registry.commands["feature-deploy"][1]
        result = asyncio.run(handler("--status"))
        self.assertIn("Feature Flags Status", result)


if __name__ == "__main__":
    unittest.main()
