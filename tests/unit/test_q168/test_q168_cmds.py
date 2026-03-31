"""Tests for Q168 CLI commands."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest

from lidco.cli.commands import q168_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ168Registration(unittest.TestCase):
    def setUp(self):
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q168_cmds.register(MockRegistry())

    def test_cc_import_registered(self):
        self.assertIn("cc-import", self.registered)

    def test_cc_compat_registered(self):
        self.assertIn("cc-compat", self.registered)

    def test_cc_hooks_registered(self):
        self.assertIn("cc-hooks", self.registered)


class TestCCImportCommand(unittest.TestCase):
    def setUp(self):
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q168_cmds.register(MockRegistry())
        self.handler = self.registered["cc-import"].handler

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_nonexistent_file(self):
        result = _run(self.handler("/nonexistent/manifest.json"))
        self.assertIn("Failed", result)

    def test_valid_manifest(self):
        data = {
            "name": "test-plugin",
            "version": "1.0.0",
            "description": "A test plugin",
            "author": "tester",
            "permissions": ["read"],
            "tools": [],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            path = f.name
        try:
            result = _run(self.handler(path))
            self.assertIn("Imported Claude Code plugin", result)
            self.assertIn("test-plugin", result)
            self.assertIn("tester", result)
        finally:
            os.unlink(path)

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json")
            path = f.name
        try:
            result = _run(self.handler(path))
            self.assertIn("Failed", result)
        finally:
            os.unlink(path)


class TestCCCompatCommand(unittest.TestCase):
    def setUp(self):
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q168_cmds.register(MockRegistry())
        self.handler = self.registered["cc-compat"].handler

    def test_scan_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            result = _run(self.handler(f"scan {td}"))
            self.assertIn("compatibility scan", result)
            self.assertIn("not found", result)

    def test_scan_with_claude_md(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "CLAUDE.md"), "w") as f:
                f.write("# Project instructions")
            result = _run(self.handler(f"scan {td}"))
            self.assertIn("found", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("badcmd"))
        self.assertIn("Usage", result)

    def test_status_alias(self):
        with tempfile.TemporaryDirectory() as td:
            result = _run(self.handler(f"status {td}"))
            self.assertIn("compatibility scan", result)


class TestCCHooksCommand(unittest.TestCase):
    def setUp(self):
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q168_cmds.register(MockRegistry())
        self.handler = self.registered["cc-hooks"].handler

    def test_list_no_path(self):
        result = _run(self.handler("list"))
        self.assertIn("Usage", result)

    def test_list_valid_hooks(self):
        settings = {
            "hooks": {
                "PreToolUse": [{"command": "echo pre", "matcher": "Bash"}],
                "Stop": ["echo bye"],
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(settings, f)
            path = f.name
        try:
            result = _run(self.handler(f"list {path}"))
            self.assertIn("2 Claude Code hook(s)", result)
            self.assertIn("echo pre", result)
        finally:
            os.unlink(path)

    def test_import_hooks(self):
        settings = {
            "hooks": {
                "PostToolUse": [{"command": "prettier"}],
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(settings, f)
            path = f.name
        try:
            result = _run(self.handler(f"import {path}"))
            self.assertIn("Imported 1 hook(s)", result)
            self.assertIn("post_tool_use", result)
        finally:
            os.unlink(path)

    def test_import_no_path(self):
        result = _run(self.handler("import"))
        self.assertIn("Usage", result)

    def test_list_no_hooks_found(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            path = f.name
        try:
            result = _run(self.handler(f"list {path}"))
            self.assertIn("No Claude Code hooks", result)
        finally:
            os.unlink(path)

    def test_unknown_subcommand(self):
        result = _run(self.handler("badcmd"))
        self.assertIn("Usage", result)
