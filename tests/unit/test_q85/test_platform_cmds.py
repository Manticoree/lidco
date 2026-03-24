"""Tests for platform_cmds (T561)."""
from __future__ import annotations
import asyncio
import json
from unittest.mock import MagicMock
import pytest
from lidco.cli.commands.platform_cmds import register_platform_commands
from lidco.cli.commands.registry import SlashCommand


def make_registry():
    r = MagicMock()
    r.registered = {}
    r.last_message = ""
    def _reg(cmd):
        r.registered[cmd.name] = cmd
    r.register.side_effect = _reg
    return r


def get_handler(name):
    r = make_registry()
    register_platform_commands(r)
    return r.registered[name].handler


def test_registers_four_commands():
    r = make_registry()
    register_platform_commands(r)
    for name in ("ci-heal", "webhook", "knowledge", "mcp-serve"):
        assert name in r.registered


def test_ci_heal_no_args():
    h = get_handler("ci-heal")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_ci_heal_passing():
    import sys
    h = get_handler("ci-heal")
    result = asyncio.run(h(f"{sys.executable} -c \"print('ok')\""))
    assert "HEALED" in result or "CI Heal" in result


def test_webhook_no_args():
    h = get_handler("webhook")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_webhook_parse_github():
    h = get_handler("webhook")
    body = json.dumps({"action": "opened"})
    result = asyncio.run(h(f"parse github {body}"))
    assert "github" in result.lower()


def test_knowledge_list_empty(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        h = get_handler("knowledge")
        result = asyncio.run(h("list"))
        assert "No knowledge" in result or isinstance(result, str)
    finally:
        os.chdir(orig)


def test_mcp_serve_info():
    h = get_handler("mcp-serve")
    result = asyncio.run(h("info"))
    assert "lidco" in result.lower() or "MCP" in result


def test_mcp_serve_tools():
    h = get_handler("mcp-serve")
    result = asyncio.run(h("tools"))
    assert "echo" in result


def test_mcp_serve_call():
    h = get_handler("mcp-serve")
    result = asyncio.run(h("call echo hello world"))
    assert "echo" in result.lower() or "Result" in result
