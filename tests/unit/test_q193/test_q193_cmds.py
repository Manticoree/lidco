"""Tests for Q193 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q193_cmds import register, _state
from lidco.cli.commands.registry import CommandRegistry


def _run(coro):
    return asyncio.run(coro)


class TestQ193CmdsRegister(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.reg = CommandRegistry()
        register(self.reg)

    def test_commands_registered(self):
        for name in ("vim", "keybindings", "macro", "repl-config"):
            cmd = self.reg._commands.get(name)
            self.assertIsNotNone(cmd, f"/{name} not registered")


class TestVimCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.reg = CommandRegistry()
        register(self.reg)
        self.handler = self.reg._commands["vim"].handler

    def test_vim_status(self):
        result = _run(self.handler(""))
        self.assertIn("Vim mode", result)

    def test_vim_enable(self):
        result = _run(self.handler("on"))
        self.assertIn("enabled", result)

    def test_vim_disable(self):
        _run(self.handler("on"))
        result = _run(self.handler("off"))
        self.assertIn("disabled", result)

    def test_vim_switch_mode(self):
        _run(self.handler("on"))
        result = _run(self.handler("insert"))
        self.assertIn("INSERT", result)

    def test_vim_unknown(self):
        result = _run(self.handler("xyz"))
        self.assertIn("Usage", result)


class TestKeybindingsCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.reg = CommandRegistry()
        register(self.reg)
        self.handler = self.reg._commands["keybindings"].handler

    def test_empty_list(self):
        result = _run(self.handler(""))
        self.assertIn("No keybindings", result)

    def test_bind(self):
        result = _run(self.handler("bind ctrl+s save"))
        self.assertIn("Bound", result)

    def test_bind_and_list(self):
        _run(self.handler("bind ctrl+s save"))
        result = _run(self.handler(""))
        self.assertIn("ctrl+s", result)

    def test_unbind(self):
        _run(self.handler("bind ctrl+s save"))
        result = _run(self.handler("unbind ctrl+s"))
        self.assertIn("Unbound", result)

    def test_export(self):
        _run(self.handler("bind ctrl+s save"))
        result = _run(self.handler("export"))
        self.assertIn('"action"', result)


class TestMacroCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.reg = CommandRegistry()
        register(self.reg)
        self.handler = self.reg._commands["macro"].handler

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_record(self):
        result = _run(self.handler("record test a b c"))
        self.assertIn("Recorded", result)
        self.assertIn("3 keys", result)

    def test_replay(self):
        _run(self.handler("record m1 x y"))
        result = _run(self.handler("replay m1"))
        self.assertIn("Replayed", result)
        self.assertIn("x y", result)

    def test_replay_not_found(self):
        result = _run(self.handler("replay nope"))
        self.assertIn("not found", result)


class TestReplConfigCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.reg = CommandRegistry()
        register(self.reg)
        self.handler = self.reg._commands["repl-config"].handler

    def test_status(self):
        result = _run(self.handler(""))
        self.assertIn("Multiline", result)
        self.assertIn("Highlight", result)

    def test_multiline_off(self):
        result = _run(self.handler("multiline off"))
        self.assertIn("off", result)

    def test_highlight_on(self):
        result = _run(self.handler("highlight on"))
        self.assertIn("on", result)

    def test_unknown(self):
        result = _run(self.handler("unknown"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
