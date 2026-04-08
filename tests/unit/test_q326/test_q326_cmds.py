"""Tests for lidco.cli.commands.q326_cmds — CLI commands."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest import mock

from lidco.cli.commands.q326_cmds import register_q326_commands


class _FakeRegistry:
    """Minimal registry for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = (description, handler)


class TestQ326Commands(unittest.TestCase):
    """Tests for Q326 CLI command registration and handlers."""

    def setUp(self) -> None:
        self.registry = _FakeRegistry()
        register_q326_commands(self.registry)

    # -- Registration ------------------------------------------------------

    def test_all_commands_registered(self) -> None:
        expected = {"config-template", "config-validate", "config-diff", "config-audit"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    # -- /config-template --------------------------------------------------

    def test_config_template_no_args(self) -> None:
        handler = self.registry.commands["config-template"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_config_template_not_found(self) -> None:
        handler = self.registry.commands["config-template"][1]
        result = asyncio.run(handler("myapp"))
        self.assertIn("not found", result)

    # -- /config-validate --------------------------------------------------

    def test_config_validate_no_args(self) -> None:
        handler = self.registry.commands["config-validate"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_config_validate_file_not_found(self) -> None:
        handler = self.registry.commands["config-validate"][1]
        result = asyncio.run(handler("/nonexistent/path.json"))
        self.assertIn("not found", result.lower())

    def test_config_validate_valid_json(self) -> None:
        handler = self.registry.commands["config-validate"][1]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"host": "localhost", "port": 5432}, f)
            f.flush()
            path = f.name
        try:
            result = asyncio.run(handler(f'"{path}"'))
            self.assertIn("valid", result.lower())
        finally:
            os.unlink(path)

    def test_config_validate_invalid_json(self) -> None:
        handler = self.registry.commands["config-validate"][1]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json at all")
            f.flush()
            path = f.name
        try:
            result = asyncio.run(handler(f'"{path}"'))
            self.assertIn("INVALID", result)
        finally:
            os.unlink(path)

    # -- /config-diff ------------------------------------------------------

    def test_config_diff_no_args(self) -> None:
        handler = self.registry.commands["config-diff"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_config_diff_file_not_found(self) -> None:
        handler = self.registry.commands["config-diff"][1]
        result = asyncio.run(handler("/nonexistent/a.json /nonexistent/b.json"))
        self.assertIn("not found", result.lower())

    def test_config_diff_two_files(self) -> None:
        handler = self.registry.commands["config-diff"][1]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f1:
            json.dump({"host": "localhost"}, f1)
            f1.flush()
            path1 = f1.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
            json.dump({"host": "prod.db"}, f2)
            f2.flush()
            path2 = f2.name
        try:
            # Quote paths for shlex on Windows (backslashes)
            result = asyncio.run(handler(f'"{path1}" "{path2}"'))
            self.assertIn("Modified", result)
        finally:
            os.unlink(path1)
            os.unlink(path2)

    # -- /config-audit -----------------------------------------------------

    def test_config_audit_no_entries(self) -> None:
        handler = self.registry.commands["config-audit"][1]
        result = asyncio.run(handler(""))
        self.assertIn("No audit entries", result)

    def test_config_audit_report_mode(self) -> None:
        handler = self.registry.commands["config-audit"][1]
        result = asyncio.run(handler("--report"))
        self.assertIn("Compliance Report", result)
        self.assertIn("Total changes: 0", result)


if __name__ == "__main__":
    unittest.main()
