"""Tests for Q144 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest

from lidco.cli.commands import q144_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ144Commands(unittest.TestCase):
    def setUp(self):
        q144_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q144_cmds.register(MockRegistry())
        self.handler = self.registered["config-migrate"].handler

    def test_command_registered(self):
        self.assertIn("config-migrate", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    # --- version ---

    def test_version_stamp(self):
        data = json.dumps({"key": "val"})
        result = _run(self.handler(f"version stamp 1.0.0 {data}"))
        self.assertIn("Stamped", result)
        self.assertIn("1.0.0", result)

    def test_version_stamp_no_data(self):
        result = _run(self.handler("version stamp"))
        self.assertIn("Usage", result)

    def test_version_get(self):
        data = json.dumps({"__config_version__": "2.0.0"})
        result = _run(self.handler(f"version get {data}"))
        self.assertIn("2.0.0", result)

    def test_version_get_no_version(self):
        data = json.dumps({"x": 1})
        result = _run(self.handler(f"version get {data}"))
        self.assertIn("No version", result)

    def test_version_compare(self):
        result = _run(self.handler("version compare 1.0.0 2.0.0"))
        self.assertIn("-1", result)

    def test_version_compare_equal(self):
        result = _run(self.handler("version compare 1.0.0 1.0.0"))
        self.assertIn("0", result)

    def test_version_unknown_sub(self):
        result = _run(self.handler("version zzz"))
        self.assertIn("Usage", result)

    # --- migrate ---

    def test_migrate_path_no_steps(self):
        result = _run(self.handler("migrate path 1.0.0 2.0.0"))
        self.assertIn("No path", result)

    def test_migrate_unknown_sub(self):
        result = _run(self.handler("migrate zzz"))
        self.assertIn("Usage", result)

    # --- backup ---

    def test_backup_list_empty(self):
        result = _run(self.handler("backup list"))
        self.assertIn("No backups", result)

    def test_backup_create_and_list(self):
        data = json.dumps({"a": 1})
        result = _run(self.handler(f"backup create 1.0.0 {data}"))
        self.assertIn("Backup created", result)
        result = _run(self.handler("backup list"))
        self.assertIn("1.0.0", result)

    def test_backup_restore_not_found(self):
        result = _run(self.handler("backup restore nonexistent"))
        self.assertIn("not found", result)

    def test_backup_delete_not_found(self):
        result = _run(self.handler("backup delete nonexistent"))
        self.assertIn("not found", result)

    def test_backup_unknown_sub(self):
        result = _run(self.handler("backup zzz"))
        self.assertIn("Usage", result)

    # --- compat ---

    def test_compat_check_clean(self):
        data = json.dumps({"key": "val"})
        result = _run(self.handler(f"compat check {data}"))
        self.assertIn("compatible", result.lower())

    def test_compat_fix_no_changes(self):
        data = json.dumps({"key": "val"})
        result = _run(self.handler(f"compat fix {data}"))
        self.assertIn("No fixes", result)

    def test_compat_unknown_sub(self):
        result = _run(self.handler("compat zzz"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
