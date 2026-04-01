"""Tests for lidco.cli.commands.q183_cmds — /sdk, /extensions, /plugin-lifecycle, /tool-builder."""

import asyncio
from unittest.mock import MagicMock

from lidco.cli.commands.q183_cmds import register


def _make_registry():
    """Create a mock registry that captures registered commands."""
    reg = MagicMock()
    reg._commands = {}

    def fake_register(cmd):
        reg._commands[cmd.name] = cmd

    reg.register = fake_register
    return reg


def test_register_commands():
    reg = _make_registry()
    register(reg)
    assert "sdk" in reg._commands
    assert "extensions" in reg._commands
    assert "plugin-lifecycle" in reg._commands
    assert "tool-builder" in reg._commands


def test_sdk_handler():
    reg = _make_registry()
    register(reg)
    result = asyncio.run(reg._commands["sdk"].handler(""))
    assert "LIDCO Plugin SDK" in result
    assert "ExtensionPointRegistry" in result
    assert "ToolBuilder" in result


def test_extensions_handler():
    reg = _make_registry()
    register(reg)
    result = asyncio.run(reg._commands["extensions"].handler(""))
    assert "No extension points defined" in result


def test_plugin_lifecycle_handler():
    reg = _make_registry()
    register(reg)
    result = asyncio.run(reg._commands["plugin-lifecycle"].handler(""))
    assert "No managed plugins" in result


def test_tool_builder_handler():
    reg = _make_registry()
    register(reg)
    result = asyncio.run(reg._commands["tool-builder"].handler(""))
    assert "ToolBuilder" in result
    assert "fluent" in result.lower() or "Fluent" in result
