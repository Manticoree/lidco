"""Tests for Q198 CLI commands — task 1106."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest


def _run(coro):
    return asyncio.run(coro)


class TestInitCommand(unittest.TestCase):
    def test_init_python_project(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        # Grab handler directly
        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        handler = cmds["init"].handler

        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "pyproject.toml"), "w").close()
            result = _run(handler(td))
            self.assertIn("python", result)

    def test_init_unknown_project(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        handler = cmds["init"].handler

        with tempfile.TemporaryDirectory() as td:
            result = _run(handler(td))
            self.assertIn("unknown", result)

    def test_init_contains_claude_md(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        handler = cmds["init"].handler

        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "pyproject.toml"), "w").close()
            result = _run(handler(td))
            self.assertIn("---", result)


class TestOnboardCommand(unittest.TestCase):
    def test_onboard_shows_progress(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        handler = cmds["onboard"].handler
        result = _run(handler(""))
        self.assertIn("0%", result)
        self.assertIn("Pending steps", result)

    def test_onboard_lists_steps(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        handler = cmds["onboard"].handler
        result = _run(handler(""))
        self.assertIn("detect_project", result)


class TestProjectTypeCommand(unittest.TestCase):
    def test_project_type_python(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        handler = cmds["project-type"].handler

        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "pyproject.toml"), "w").close()
            result = _run(handler(td))
            self.assertIn("python", result)

    def test_project_type_with_frameworks(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        handler = cmds["project-type"].handler

        with tempfile.TemporaryDirectory() as td:
            pkg = {"dependencies": {"react": "^18.0"}}
            with open(os.path.join(td, "package.json"), "w") as f:
                json.dump(pkg, f)
            result = _run(handler(td))
            self.assertIn("react", result)


class TestSetupCheckCommand(unittest.TestCase):
    def test_setup_check_no_claude_md(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        handler = cmds["setup-check"].handler

        with tempfile.TemporaryDirectory() as td:
            result = _run(handler(td))
            self.assertIn("[ ] claude_md", result)

    def test_setup_check_with_claude_md(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        handler = cmds["setup-check"].handler

        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "CLAUDE.md"), "w") as f:
                f.write("# Test")
            open(os.path.join(td, "pyproject.toml"), "w").close()
            result = _run(handler(td))
            self.assertIn("[x] claude_md", result)
            self.assertIn("[x] project_detected", result)

    def test_setup_check_shows_percentage(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        handler = cmds["setup-check"].handler

        with tempfile.TemporaryDirectory() as td:
            result = _run(handler(td))
            self.assertIn("complete", result)


class TestCommandRegistration(unittest.TestCase):
    def test_all_commands_registered(self):
        from lidco.cli.commands.q198_cmds import register as _reg

        cmds: dict = {}

        class FakeRegistry:
            def register(self, cmd):
                cmds[cmd.name] = cmd

        _reg(FakeRegistry())
        self.assertIn("init", cmds)
        self.assertIn("onboard", cmds)
        self.assertIn("project-type", cmds)
        self.assertIn("setup-check", cmds)
