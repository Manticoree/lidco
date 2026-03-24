"""Tests for nav_cmds (T566)."""
from __future__ import annotations
import asyncio
from unittest.mock import MagicMock
import pytest
from lidco.cli.commands.nav_cmds import register_nav_commands
from lidco.cli.commands.registry import SlashCommand


def make_registry():
    r = MagicMock()
    r.registered = {}
    def _reg(cmd):
        r.registered[cmd.name] = cmd
    r.register.side_effect = _reg
    return r


def get_handler(name):
    r = make_registry()
    register_nav_commands(r)
    return r.registered[name].handler


def test_registers_four_commands():
    r = make_registry()
    register_nav_commands(r)
    for name in ("navigate", "code-explain", "refactor-suggest", "fix-error"):
        assert name in r.registered


def test_navigate_no_args():
    h = get_handler("navigate")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_navigate_symbol(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "m.py").write_text("def my_sym(): pass\nmy_sym()\n")
        h = get_handler("navigate")
        result = asyncio.run(h("my_sym"))
        assert "my_sym" in result
    finally:
        os.chdir(orig)


def test_explain_no_args():
    h = get_handler("code-explain")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_explain_file(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        p = tmp_path / "mod.py"
        p.write_text("def foo(): pass\n")
        h = get_handler("code-explain")
        result = asyncio.run(h(str(p)))
        assert "mod.py" in result or "foo" in result
    finally:
        os.chdir(orig)


def test_refactor_suggest_no_args():
    h = get_handler("refactor-suggest")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_refactor_suggest_file(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        p = tmp_path / "big.py"
        p.write_text("def big(a,b,c,d,e,f):\n" + "    x = 1\n" * 50)
        h = get_handler("refactor-suggest")
        result = asyncio.run(h(str(p)))
        assert isinstance(result, str)
    finally:
        os.chdir(orig)


def test_fix_error_no_args():
    h = get_handler("fix-error")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_fix_error_traceback():
    h = get_handler("fix-error")
    tb = "Traceback:\n  File x.py, line 1\nKeyError: 'missing'"
    result = asyncio.run(h(tb))
    assert "KeyError" in result or "Error" in result
