"""Tests for lidco.cli.commands.q323_cmds — CLI commands."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q323_cmds import register_q323_commands


class _FakeRegistry:
    """Minimal registry stub that captures registered commands."""

    def __init__(self) -> None:
        self.commands: dict[str, object] = {}
        self.handlers: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = description
        self.handlers[name] = handler


class TestQ323CmdsRegistration(unittest.TestCase):
    def test_all_commands_registered(self) -> None:
        reg = _FakeRegistry()
        register_q323_commands(reg)
        expected = {"service-map", "traffic-analyze", "circuit-config", "rate-config"}
        self.assertEqual(set(reg.commands.keys()), expected)


class TestServiceMapHandler(unittest.TestCase):
    def _get_handler(self) -> object:
        reg = _FakeRegistry()
        register_q323_commands(reg)
        return reg.handlers["service-map"]

    def test_empty(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("No services discovered", result)

    def test_with_unhealthy_flag(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--unhealthy"))
        # No services registered at all
        self.assertIn("No services discovered", result)


class TestTrafficAnalyzeHandler(unittest.TestCase):
    def _get_handler(self) -> object:
        reg = _FakeRegistry()
        register_q323_commands(reg)
        return reg.handlers["traffic-analyze"]

    def test_empty(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("No traffic data", result)

    def test_with_top_flag(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--top 5"))
        self.assertIn("No traffic data", result)


class TestCircuitConfigHandler(unittest.TestCase):
    def _get_handler(self) -> object:
        reg = _FakeRegistry()
        register_q323_commands(reg)
        return reg.handlers["circuit-config"]

    def test_empty(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("No failure data", result)

    def test_with_service_flag(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--service api"))
        self.assertIn("Circuit Breaker Config for api", result)
        self.assertIn("Failure threshold", result)


class TestRateConfigHandler(unittest.TestCase):
    def _get_handler(self) -> object:
        reg = _FakeRegistry()
        register_q323_commands(reg)
        return reg.handlers["rate-config"]

    def test_empty(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("No capacity data", result)

    def test_with_margin_flag(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--margin 0.9 --burst 3.0"))
        self.assertIn("No capacity data", result)


if __name__ == "__main__":
    unittest.main()
