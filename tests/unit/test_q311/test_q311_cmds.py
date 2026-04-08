"""Tests for lidco.cli.commands.q311_cmds."""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock


class _FakeRegistry:
    """Minimal registry mock for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = (description, handler)


class TestQ311Commands(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q311_cmds import register_q311_commands

        self.registry = _FakeRegistry()
        register_q311_commands(self.registry)

    def test_all_commands_registered(self) -> None:
        expected = {
            "chaos-experiment",
            "inject-fault",
            "chaos-monitor",
            "resilience-score",
        }
        self.assertEqual(set(self.registry.commands.keys()), expected)

    # -- /chaos-experiment -------------------------------------------------

    def test_chaos_experiment_no_args(self) -> None:
        handler = self.registry.commands["chaos-experiment"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_chaos_experiment_invalid_type(self) -> None:
        handler = self.registry.commands["chaos-experiment"][1]
        result = asyncio.run(handler("bogus_type"))
        self.assertIn("Unknown experiment type", result)

    def test_chaos_experiment_network_delay(self) -> None:
        handler = self.registry.commands["chaos-experiment"][1]
        result = asyncio.run(handler("network_delay --duration 5 --intensity 0.8"))
        self.assertIn("network_delay", result)
        self.assertIn("5.0s", result)
        self.assertIn("running", result)

    def test_chaos_experiment_with_scope_and_target(self) -> None:
        handler = self.registry.commands["chaos-experiment"][1]
        result = asyncio.run(
            handler("disk_full --scope global --target storage --duration 10")
        )
        self.assertIn("disk_full", result)
        self.assertIn("global", result)

    def test_chaos_experiment_invalid_intensity(self) -> None:
        handler = self.registry.commands["chaos-experiment"][1]
        result = asyncio.run(handler("cpu_spike --intensity 5.0"))
        self.assertIn("Invalid config", result)

    # -- /inject-fault -----------------------------------------------------

    def test_inject_fault_no_args(self) -> None:
        handler = self.registry.commands["inject-fault"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_inject_fault_invalid_type(self) -> None:
        handler = self.registry.commands["inject-fault"][1]
        result = asyncio.run(handler("bogus"))
        self.assertIn("Unknown fault type", result)

    def test_inject_fault_missing_target(self) -> None:
        handler = self.registry.commands["inject-fault"][1]
        result = asyncio.run(handler("timeout"))
        self.assertIn("--target is required", result)

    def test_inject_fault_success(self) -> None:
        handler = self.registry.commands["inject-fault"][1]
        result = asyncio.run(
            handler("timeout --target api-service --duration 5 --probability 0.5")
        )
        self.assertIn("Fault injected", result)
        self.assertIn("timeout", result)
        self.assertIn("api-service", result)
        self.assertIn("active", result)

    def test_inject_fault_error_response(self) -> None:
        handler = self.registry.commands["inject-fault"][1]
        result = asyncio.run(handler("error_response --target db"))
        self.assertIn("error_response", result)

    # -- /chaos-monitor ----------------------------------------------------

    def test_chaos_monitor_default(self) -> None:
        handler = self.registry.commands["chaos-monitor"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Chaos Monitor Status", result)
        self.assertIn("healthy", result)
        self.assertIn("0.999", result)

    def test_chaos_monitor_custom_sla(self) -> None:
        handler = self.registry.commands["chaos-monitor"][1]
        result = asyncio.run(handler("--sla-target 0.95"))
        self.assertIn("0.95", result)

    # -- /resilience-score -------------------------------------------------

    def test_resilience_score_default(self) -> None:
        handler = self.registry.commands["resilience-score"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Resilience Score", result)
        self.assertIn("0.0", result)
        self.assertIn("F", result)

    def test_resilience_score_custom_target(self) -> None:
        handler = self.registry.commands["resilience-score"][1]
        result = asyncio.run(handler("--recovery-target 10"))
        self.assertIn("Resilience Score", result)


if __name__ == "__main__":
    unittest.main()
