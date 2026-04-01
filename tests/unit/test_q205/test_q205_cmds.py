"""Tests for lidco.cli.commands.q205_cmds."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from lidco.cli.commands.q205_cmds import register


class _FakeRegistry:
    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ205Commands:
    def setup_method(self):
        self.reg = _FakeRegistry()
        register(self.reg)

    def test_all_commands_registered(self):
        expected = {"render-mode", "terminal-info", "status-line", "color"}
        assert set(self.reg.commands.keys()) == expected

    def test_render_mode_no_args(self):
        handler = self.reg.commands["render-mode"].handler
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_render_mode_valid(self):
        handler = self.reg.commands["render-mode"].handler
        result = asyncio.run(handler("normal"))
        assert "normal" in result

    def test_render_mode_invalid(self):
        handler = self.reg.commands["render-mode"].handler
        result = asyncio.run(handler("badmode"))
        assert "Unknown mode" in result

    def test_terminal_info(self):
        handler = self.reg.commands["terminal-info"].handler
        with patch.dict("os.environ", {}, clear=True):
            with patch("os.get_terminal_size", side_effect=OSError):
                result = asyncio.run(handler(""))
                assert "Terminal:" in result

    def test_status_line_demo(self):
        handler = self.reg.commands["status-line"].handler
        result = asyncio.run(handler("demo"))
        assert "model" in result

    def test_status_line_no_args(self):
        handler = self.reg.commands["status-line"].handler
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_color_handler(self):
        handler = self.reg.commands["color"].handler
        result = asyncio.run(handler("test"))
        assert "test" in result
