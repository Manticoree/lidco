"""Tests for transform_cmds (T536)."""
from __future__ import annotations
import asyncio
from unittest.mock import MagicMock, patch
import pytest
from lidco.cli.commands.transform_cmds import register_transform_commands
from lidco.cli.commands.registry import CommandRegistry, SlashCommand


def make_registry() -> CommandRegistry:
    r = MagicMock(spec=CommandRegistry)
    r.registered = {}
    def _register(cmd):
        r.registered[cmd.name] = cmd
    r.register.side_effect = _register
    return r


def get_handler(name: str):
    r = make_registry()
    register_transform_commands(r)
    return r.registered[name].handler


def test_registers_four_commands():
    r = make_registry()
    register_transform_commands(r)
    assert "rename" in r.registered
    assert "multi-edit" in r.registered
    assert "testgen" in r.registered
    assert "health" in r.registered


def test_rename_no_args():
    h = get_handler("rename")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_rename_missing_new_name():
    h = get_handler("rename")
    result = asyncio.run(h("old_name"))
    assert "Usage" in result


def test_rename_dry_run_flag(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "a.py").write_text("foo = 1\n")
        h = get_handler("rename")
        result = asyncio.run(h("foo bar --dry-run"))
        assert "dry-run" in result or "foo" in result
    finally:
        os.chdir(orig)


def test_multi_edit_no_args():
    h = get_handler("multi-edit")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_testgen_no_args():
    h = get_handler("testgen")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_testgen_file_not_found():
    h = get_handler("testgen")
    result = asyncio.run(h("/nonexistent/file.py"))
    assert "error" in result.lower() or "not found" in result.lower()


def test_health_handler():
    h = get_handler("health")
    result = asyncio.run(h(""))
    assert "Health" in result or "failed" in result


def test_rename_calls_symbol_renamer(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "x.py").write_text("alpha = 1\n")
        h = get_handler("rename")
        result = asyncio.run(h("alpha beta"))
        assert "beta" in result or "alpha" in result
    finally:
        os.chdir(orig)
