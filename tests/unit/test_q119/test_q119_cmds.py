"""Tests for Q119 CLI commands — Task 731."""

from __future__ import annotations

import asyncio
import json
import unittest

from lidco.cli.commands.q119_cmds import register, _state
from lidco.cli.commands.registry import CommandRegistry


def _run(coro):
    return asyncio.run(coro)


def _make_registry():
    """Create a bare CommandRegistry with only q119 commands."""
    # Avoid full _register_builtins by creating a minimal registry
    reg = object.__new__(CommandRegistry)
    reg._commands = {}
    reg._session = None
    register(reg)
    return reg


class TestRulesListCommand(unittest.TestCase):
    """Test /rules list."""

    def setUp(self):
        _state.clear()

    def test_rules_list_no_loader(self):
        reg = _make_registry()
        cmd = reg.get("rules")
        result = _run(cmd.handler("list"))
        # Should use default loader, likely empty
        self.assertIsInstance(result, str)

    def test_rules_list_with_injected_loader(self):
        from lidco.rules.rules_loader import RulesFile, RulesFileLoader

        loader = RulesFileLoader(
            rules_dir="/d",
            read_fn=lambda p: '---\nglobs: "*.py"\n---\nPython rule',
            listdir_fn=lambda d: ["py.md"],
            mtime_fn=lambda p: 1.0,
        )
        _state["rules_loader"] = loader
        reg = _make_registry()
        cmd = reg.get("rules")
        result = _run(cmd.handler("list"))
        self.assertIn("py.md", result)
        self.assertIn("*.py", result)

    def test_rules_list_empty(self):
        from lidco.rules.rules_loader import RulesFileLoader

        loader = RulesFileLoader(
            rules_dir="/d",
            read_fn=lambda p: "",
            listdir_fn=lambda d: [],
            mtime_fn=lambda p: 0,
        )
        _state["rules_loader"] = loader
        reg = _make_registry()
        cmd = reg.get("rules")
        result = _run(cmd.handler("list"))
        self.assertIn("no rules", result.lower())


class TestRulesCheckCommand(unittest.TestCase):
    """Test /rules check <file>."""

    def setUp(self):
        _state.clear()

    def test_rules_check_matching_file(self):
        from lidco.rules.rules_loader import RulesFileLoader

        loader = RulesFileLoader(
            rules_dir="/d",
            read_fn=lambda p: '---\nglobs: "*.py"\n---\nPython rule',
            listdir_fn=lambda d: ["py.md"],
            mtime_fn=lambda p: 1.0,
        )
        _state["rules_loader"] = loader
        reg = _make_registry()
        cmd = reg.get("rules")
        result = _run(cmd.handler("check main.py"))
        self.assertIn("py.md", result)

    def test_rules_check_no_match(self):
        from lidco.rules.rules_loader import RulesFileLoader

        loader = RulesFileLoader(
            rules_dir="/d",
            read_fn=lambda p: '---\nglobs: "*.py"\n---\nPython',
            listdir_fn=lambda d: ["py.md"],
            mtime_fn=lambda p: 1.0,
        )
        _state["rules_loader"] = loader
        reg = _make_registry()
        cmd = reg.get("rules")
        result = _run(cmd.handler("check app.js"))
        self.assertIn("no rules", result.lower())

    def test_rules_check_no_file_arg(self):
        reg = _make_registry()
        cmd = reg.get("rules")
        result = _run(cmd.handler("check"))
        self.assertIn("usage", result.lower())

    def test_rules_usage_no_sub(self):
        reg = _make_registry()
        cmd = reg.get("rules")
        result = _run(cmd.handler(""))
        self.assertIn("usage", result.lower())


class TestEffortCommand(unittest.TestCase):
    """Test /effort commands."""

    def setUp(self):
        _state.clear()

    def test_effort_show_default(self):
        reg = _make_registry()
        cmd = reg.get("effort")
        result = _run(cmd.handler(""))
        self.assertIn("medium", result.lower())

    def test_effort_set_low(self):
        reg = _make_registry()
        cmd = reg.get("effort")
        result = _run(cmd.handler("low"))
        self.assertIn("low", result.lower())

    def test_effort_set_high(self):
        reg = _make_registry()
        cmd = reg.get("effort")
        result = _run(cmd.handler("high"))
        self.assertIn("high", result.lower())

    def test_effort_set_auto(self):
        reg = _make_registry()
        cmd = reg.get("effort")
        result = _run(cmd.handler("auto"))
        self.assertIn("auto", result.lower())

    def test_effort_auto_with_word_count(self):
        reg = _make_registry()
        cmd = reg.get("effort")
        result = _run(cmd.handler("auto 3"))
        self.assertIn("low", result.lower())

    def test_effort_auto_high_word_count(self):
        reg = _make_registry()
        cmd = reg.get("effort")
        result = _run(cmd.handler("auto 100"))
        self.assertIn("high", result.lower())

    def test_effort_invalid_level(self):
        reg = _make_registry()
        cmd = reg.get("effort")
        result = _run(cmd.handler("ultra"))
        self.assertIn("invalid", result.lower())

    def test_effort_shows_budget(self):
        reg = _make_registry()
        cmd = reg.get("effort")
        result = _run(cmd.handler(""))
        self.assertIn("token", result.lower())

    def test_effort_set_medium(self):
        reg = _make_registry()
        cmd = reg.get("effort")
        result = _run(cmd.handler("medium"))
        self.assertIn("medium", result.lower())


class TestColorCommand(unittest.TestCase):
    """Test /color commands."""

    def setUp(self):
        _state.clear()

    def test_color_show_default(self):
        reg = _make_registry()
        cmd = reg.get("color")
        result = _run(cmd.handler(""))
        self.assertIn("no color", result.lower())

    def test_color_set_red(self):
        reg = _make_registry()
        cmd = reg.get("color")
        result = _run(cmd.handler("red"))
        self.assertIn("red", result.lower())

    def test_color_set_hex(self):
        reg = _make_registry()
        cmd = reg.get("color")
        result = _run(cmd.handler("#FF0000"))
        self.assertIn("#FF0000", result)

    def test_color_reset(self):
        reg = _make_registry()
        cmd = reg.get("color")
        _run(cmd.handler("blue"))
        result = _run(cmd.handler("reset"))
        self.assertIn("reset", result.lower())

    def test_color_list(self):
        reg = _make_registry()
        cmd = reg.get("color")
        result = _run(cmd.handler("list"))
        self.assertIn("red", result)
        self.assertIn("blue", result)
        self.assertIn("green", result)

    def test_color_invalid(self):
        reg = _make_registry()
        cmd = reg.get("color")
        result = _run(cmd.handler("chartreuse"))
        self.assertIn("error", result.lower())

    def test_color_after_set_show(self):
        reg = _make_registry()
        cmd = reg.get("color")
        _run(cmd.handler("cyan"))
        result = _run(cmd.handler(""))
        self.assertIn("cyan", result.lower())


class TestCommandRegistration(unittest.TestCase):
    """Verify all commands registered."""

    def test_rules_registered(self):
        reg = _make_registry()
        self.assertIsNotNone(reg.get("rules"))

    def test_effort_registered(self):
        reg = _make_registry()
        self.assertIsNotNone(reg.get("effort"))

    def test_color_registered(self):
        reg = _make_registry()
        self.assertIsNotNone(reg.get("color"))

    def test_commands_have_descriptions(self):
        reg = _make_registry()
        for name in ("rules", "effort", "color"):
            cmd = reg.get(name)
            self.assertTrue(len(cmd.description) > 0)


if __name__ == "__main__":
    unittest.main()
