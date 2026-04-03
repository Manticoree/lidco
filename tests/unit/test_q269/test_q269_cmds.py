"""Tests for src/lidco/cli/commands/q269_cmds.py."""
from __future__ import annotations

import asyncio
import json


class _FakeRegistry:
    """Minimal command registry for testing."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register_async(self, name, description, handler):
        self.commands[name] = handler


def _setup():
    from lidco.cli.commands.q269_cmds import register_q269_commands

    reg = _FakeRegistry()
    register_q269_commands(reg)
    return reg


class TestThemeCmd:
    def test_no_args_shows_usage(self):
        reg = _setup()
        result = asyncio.run(reg.commands["theme"](""))
        assert "Usage" in result

    def test_list(self):
        reg = _setup()
        result = asyncio.run(reg.commands["theme"]("list"))
        assert "dark" in result

    def test_set_valid(self):
        reg = _setup()
        result = asyncio.run(reg.commands["theme"]("set light"))
        assert "light" in result

    def test_set_invalid(self):
        reg = _setup()
        result = asyncio.run(reg.commands["theme"]("set nonexistent"))
        assert "not found" in result

    def test_info(self):
        reg = _setup()
        result = asyncio.run(reg.commands["theme"]("info dark"))
        assert "dark" in result

    def test_create(self):
        reg = _setup()
        colors_json = json.dumps({"bg": "#111"})
        result = asyncio.run(reg.commands["theme"](f"create mytest '{colors_json}'"))
        assert "mytest" in result


class TestColorsCmd:
    def test_no_args(self):
        reg = _setup()
        result = asyncio.run(reg.commands["colors"](""))
        assert "Usage" in result

    def test_list(self):
        reg = _setup()
        result = asyncio.run(reg.commands["colors"]("list"))
        assert "red" in result


class TestIconsCmd:
    def test_list(self):
        reg = _setup()
        result = asyncio.run(reg.commands["icons"]("list"))
        assert "success" in result

    def test_toggle(self):
        reg = _setup()
        result = asyncio.run(reg.commands["icons"]("toggle-unicode"))
        assert "toggled" in result


class TestThemeExportCmd:
    def test_export(self):
        reg = _setup()
        result = asyncio.run(reg.commands["theme-export"]("export dark"))
        data = json.loads(result)
        assert data["name"] == "dark"

    def test_import(self):
        reg = _setup()
        theme_json = json.dumps({"name": "imported", "colors": {"bg": "#000"}})
        result = asyncio.run(reg.commands["theme-export"](f"import '{theme_json}'"))
        assert "imported" in result
