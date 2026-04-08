"""Tests for lidco.cli.commands.q325_cmds — CLI commands."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    """Captures registrations for testing."""

    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler) -> None:
        self.commands[name] = (desc, handler)


class TestQ325CommandRegistration(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q325_cmds import register_q325_commands

        self.registry = _FakeRegistry()
        register_q325_commands(self.registry)

    def test_all_commands_registered(self) -> None:
        expected = {"env-provision", "env-compare", "env-promote", "env-monitor"}
        self.assertEqual(set(self.registry.commands.keys()), expected)


class TestEnvProvisionCommand(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q325_cmds import register_q325_commands

        self.registry = _FakeRegistry()
        register_q325_commands(self.registry)
        self.handler = self.registry.commands["env-provision"][1]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_provision_template(self) -> None:
        result = _run(self.handler("web-app"))
        self.assertIn("Provisioned", result)
        self.assertIn("web-app", result)

    def test_provision_with_name(self) -> None:
        result = _run(self.handler("myapp --name custom-env"))
        self.assertIn("custom-env", result)

    def test_provision_with_tier(self) -> None:
        result = _run(self.handler("myapp --tier staging"))
        self.assertIn("staging", result)

    def test_provision_invalid_tier(self) -> None:
        result = _run(self.handler("myapp --tier bogus"))
        self.assertIn("Invalid tier", result)

    def test_list_empty(self) -> None:
        result = _run(self.handler("--list"))
        self.assertIn("No environments", result)

    def test_list_invalid_tier(self) -> None:
        result = _run(self.handler("--list --tier bogus"))
        self.assertIn("Invalid tier", result)

    def test_destroy_no_id(self) -> None:
        result = _run(self.handler("--destroy"))
        self.assertIn("Usage", result)

    def test_destroy_missing_env(self) -> None:
        result = _run(self.handler("--destroy nonexistent"))
        self.assertIn("Error", result)


class TestEnvCompareCommand(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q325_cmds import register_q325_commands

        self.registry = _FakeRegistry()
        register_q325_commands(self.registry)
        self.handler = self.registry.commands["env-compare"][1]

    def test_no_args(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_one_arg(self) -> None:
        result = _run(self.handler("env1"))
        self.assertIn("Usage", result)

    def test_compare(self) -> None:
        result = _run(self.handler("env1 env2"))
        self.assertIn("Comparing", result)
        self.assertIn("env1", result)
        self.assertIn("env2", result)


class TestEnvPromoteCommand(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q325_cmds import register_q325_commands

        self.registry = _FakeRegistry()
        register_q325_commands(self.registry)
        self.handler = self.registry.commands["env-promote"][1]

    def test_no_args(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_promote(self) -> None:
        result = _run(self.handler("src tgt"))
        self.assertIn("Promotion", result)
        self.assertIn("src", result)
        self.assertIn("tgt", result)

    def test_promote_with_approver(self) -> None:
        result = _run(self.handler("src tgt --approve alice"))
        self.assertIn("alice", result)

    def test_rollback(self) -> None:
        result = _run(self.handler("--rollback promo123"))
        self.assertIn("Rollback", result)
        self.assertIn("promo123", result)

    def test_rollback_no_id(self) -> None:
        result = _run(self.handler("--rollback"))
        self.assertIn("Usage", result)

    def test_one_arg(self) -> None:
        result = _run(self.handler("onlysrc"))
        self.assertIn("Usage", result)


class TestEnvMonitorCommand(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q325_cmds import register_q325_commands

        self.registry = _FakeRegistry()
        register_q325_commands(self.registry)
        self.handler = self.registry.commands["env-monitor"][1]

    def test_no_args(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Monitoring all", result)

    def test_specific_env(self) -> None:
        result = _run(self.handler("--env abc123"))
        self.assertIn("abc123", result)

    def test_expired_flag(self) -> None:
        result = _run(self.handler("--expired"))
        self.assertIn("expired", result.lower())


if __name__ == "__main__":
    unittest.main()
