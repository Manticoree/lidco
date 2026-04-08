"""Tests for lidco.cli.commands.q324_cmds — /backup, /dr-plan, /failover, /dr-test."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class FakeRegistry:
    """Minimal registry mock for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler: object) -> None:
        self.commands[name] = (desc, handler)


class TestQ324CmdsRegistration(unittest.TestCase):
    def test_all_commands_registered(self) -> None:
        from lidco.cli.commands.q324_cmds import register_q324_commands

        reg = FakeRegistry()
        register_q324_commands(reg)
        self.assertIn("backup", reg.commands)
        self.assertIn("dr-plan", reg.commands)
        self.assertIn("failover", reg.commands)
        self.assertIn("dr-test", reg.commands)
        self.assertEqual(len(reg.commands), 4)


class TestBackupCommand(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q324_cmds import register_q324_commands

        reg = FakeRegistry()
        register_q324_commands(reg)
        return reg.commands["backup"][1]

    def test_backup_default(self) -> None:
        handler = self._get_handler()
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            Path(td, "file.txt").write_text("data")
            quoted = f'"{td}"'
            result = asyncio.run(handler(quoted))
            self.assertIn("Backup", result)
            self.assertIn("completed", result)

    def test_backup_nonexistent(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler('"/nonexistent/path/q324"'))
        self.assertIn("failed", result)

    def test_backup_with_type(self) -> None:
        handler = self._get_handler()
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            Path(td, "x.txt").write_text("x")
            result = asyncio.run(handler(f'--type full "{td}"'))
            self.assertIn("full", result)


class TestDRPlanCommand(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q324_cmds import register_q324_commands

        reg = FakeRegistry()
        register_q324_commands(reg)
        return reg.commands["dr-plan"][1]

    def test_default(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("DR Plan", result)
        self.assertIn("RTO target", result)
        self.assertIn("Components", result)

    def test_custom_name(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--name MyPlan"))
        self.assertIn("MyPlan", result)

    def test_custom_rto(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--rto 7200"))
        self.assertIn("7200", result)


class TestFailoverCommand(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q324_cmds import register_q324_commands

        reg = FakeRegistry()
        register_q324_commands(reg)
        return reg.commands["failover"][1]

    def test_default(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("Failover", result)
        self.assertIn("completed", result)

    def test_status(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--status"))
        self.assertIn("Node Health", result)


class TestDRTestCommand(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q324_cmds import register_q324_commands

        reg = FakeRegistry()
        register_q324_commands(reg)
        return reg.commands["dr-test"][1]

    def test_default(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("DR Test", result)
        self.assertIn("passed", result)

    def test_custom_scenario(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--scenario backup_restore"))
        self.assertIn("backup_restore", result)


if __name__ == "__main__":
    unittest.main()
