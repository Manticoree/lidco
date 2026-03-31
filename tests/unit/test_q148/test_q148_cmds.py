"""Tests for Q148 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ148Registration(unittest.TestCase):
    def test_register_maintenance_command(self):
        from lidco.cli.commands.q148_cmds import register
        reg = _FakeRegistry()
        register(reg)
        self.assertIn("maintenance", reg.commands)

    def test_command_description(self):
        from lidco.cli.commands.q148_cmds import register
        reg = _FakeRegistry()
        register(reg)
        cmd = reg.commands["maintenance"]
        self.assertIn("Q148", cmd.description)


class TestMaintenanceClean(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q148_cmds import register
        reg = _FakeRegistry()
        register(reg)
        return reg.commands["maintenance"].handler

    @patch("lidco.maintenance.temp_cleaner.TempCleaner.clean")
    def test_clean_subcommand(self, mock_clean):
        from lidco.maintenance.temp_cleaner import CleanupResult
        mock_clean.return_value = CleanupResult(removed=["a.pyc"], bytes_freed=100)
        handler = self._get_handler()
        result = _run(handler("clean ."))
        self.assertIn("Removed: 1", result)
        self.assertIn("100", result)

    @patch("lidco.maintenance.temp_cleaner.TempCleaner.clean")
    def test_clean_dry_run(self, mock_clean):
        from lidco.maintenance.temp_cleaner import CleanupResult
        mock_clean.return_value = CleanupResult(skipped=["a.pyc"])
        handler = self._get_handler()
        result = _run(handler("clean . --dry-run"))
        self.assertIn("Skipped: 1", result)

    @patch("lidco.maintenance.temp_cleaner.TempCleaner.clean")
    def test_clean_with_errors(self, mock_clean):
        from lidco.maintenance.temp_cleaner import CleanupResult
        mock_clean.return_value = CleanupResult(errors=["fail"])
        handler = self._get_handler()
        result = _run(handler("clean ."))
        self.assertIn("Errors: 1", result)


class TestMaintenanceEstimate(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q148_cmds import register
        reg = _FakeRegistry()
        register(reg)
        return reg.commands["maintenance"].handler

    @patch("lidco.maintenance.temp_cleaner.TempCleaner.estimate")
    def test_estimate(self, mock_est):
        mock_est.return_value = {"total_files": 5, "total_bytes": 500}
        handler = self._get_handler()
        result = _run(handler("estimate ."))
        data = json.loads(result)
        self.assertEqual(data["total_files"], 5)


class TestMaintenanceOrphans(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q148_cmds import register
        reg = _FakeRegistry()
        register(reg)
        return reg.commands["maintenance"].handler

    def test_orphans_stub(self):
        handler = self._get_handler()
        result = _run(handler("orphans"))
        self.assertIn("stub", result.lower())


class TestMaintenanceDisk(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q148_cmds import register
        reg = _FakeRegistry()
        register(reg)
        return reg.commands["maintenance"].handler

    @patch("lidco.maintenance.disk_usage.DiskUsageAnalyzer.largest")
    @patch("lidco.maintenance.disk_usage.DiskUsageAnalyzer.format_tree")
    def test_disk_subcommand(self, mock_tree, mock_largest):
        mock_largest.return_value = []
        mock_tree.return_value = "(empty)"
        handler = self._get_handler()
        result = _run(handler("disk ."))
        self.assertIn("empty", result)


class TestMaintenanceHealth(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q148_cmds import register
        reg = _FakeRegistry()
        register(reg)
        return reg.commands["maintenance"].handler

    def test_health_subcommand(self):
        handler = self._get_handler()
        result = _run(handler("health"))
        self.assertIn("Health", result)
        self.assertIn("A", result)


class TestMaintenanceUsage(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q148_cmds import register
        reg = _FakeRegistry()
        register(reg)
        return reg.commands["maintenance"].handler

    def test_no_subcommand(self):
        handler = self._get_handler()
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        handler = self._get_handler()
        result = _run(handler("unknown"))
        self.assertIn("Usage", result)

    def test_usage_lists_subcommands(self):
        handler = self._get_handler()
        result = _run(handler(""))
        self.assertIn("clean", result)
        self.assertIn("orphans", result)
        self.assertIn("disk", result)
        self.assertIn("health", result)

    def test_usage_lists_estimate(self):
        handler = self._get_handler()
        result = _run(handler(""))
        self.assertIn("estimate", result)


if __name__ == "__main__":
    unittest.main()
