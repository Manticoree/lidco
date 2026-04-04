"""Tests for Q306 CLI commands."""

import asyncio
import json
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock


class _FakeRegistry:
    """Minimal registry to capture registrations."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = handler


def _build_registry() -> _FakeRegistry:
    from lidco.cli.commands.q306_cmds import register_q306_commands
    reg = _FakeRegistry()
    register_q306_commands(reg)
    return reg


class TestQ306Commands(unittest.TestCase):
    def test_registers_monorepo(self):
        reg = _build_registry()
        self.assertIn("monorepo", reg.commands)

    def test_registers_affected(self):
        reg = _build_registry()
        self.assertIn("affected", reg.commands)

    def test_registers_dep_graph(self):
        reg = _build_registry()
        self.assertIn("dep-graph", reg.commands)

    def test_registers_publish(self):
        reg = _build_registry()
        self.assertIn("publish", reg.commands)

    def test_affected_no_args(self):
        reg = _build_registry()
        handler = reg.commands["affected"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_publish_no_args(self):
        reg = _build_registry()
        handler = reg.commands["publish"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_monorepo_detect_empty(self):
        """Test /monorepo detect on a temp dir with no monorepo markers."""
        reg = _build_registry()
        handler = reg.commands["monorepo"]
        tmp = Path(tempfile.mkdtemp())
        try:
            result = asyncio.run(handler(f"detect {tmp}"))
            self.assertIn("Monorepo tool: none", result)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_monorepo_config_empty(self):
        reg = _build_registry()
        handler = reg.commands["monorepo"]
        tmp = Path(tempfile.mkdtemp())
        try:
            result = asyncio.run(handler(f"config {tmp}"))
            self.assertIn("No workspace config found", result)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_dep_graph_unknown_subcmd(self):
        reg = _build_registry()
        handler = reg.commands["dep-graph"]
        result = asyncio.run(handler("unknown"))
        self.assertIn("Unknown subcommand", result)

    def test_publish_unknown_subcmd(self):
        reg = _build_registry()
        handler = reg.commands["publish"]
        result = asyncio.run(handler("unknown"))
        self.assertIn("Unknown subcommand", result)


if __name__ == "__main__":
    unittest.main()
