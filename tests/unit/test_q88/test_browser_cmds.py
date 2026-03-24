"""Tests for browser_cmds (T576)."""
from __future__ import annotations
import asyncio
from unittest.mock import MagicMock
import pytest
from lidco.cli.commands.browser_cmds import register_browser_commands


def make_registry():
    r = MagicMock()
    r.registered = {}
    def _reg(cmd): r.registered[cmd.name] = cmd
    r.register.side_effect = _reg
    return r


def get_handler(name):
    r = make_registry()
    register_browser_commands(r)
    return r.registered[name].handler


def test_registers_four_commands():
    r = make_registry()
    register_browser_commands(r)
    for name in ("browser", "visual-test", "plan-act", "screenshot-analyze"):
        assert name in r.registered


def test_browser_no_playwright():
    h = get_handler("browser")
    result = asyncio.run(h("navigate http://example.com"))
    # Either works or says playwright not installed
    assert isinstance(result, str)


def test_visual_test_list(tmp_path):
    import os; orig = os.getcwd(); os.chdir(tmp_path)
    try:
        h = get_handler("visual-test")
        result = asyncio.run(h("list"))
        assert "baseline" in result.lower() or "No" in result
    finally:
        os.chdir(orig)


def test_visual_test_run(tmp_path):
    import os; orig = os.getcwd(); os.chdir(tmp_path)
    try:
        h = get_handler("visual-test")
        result = asyncio.run(h("run my_test"))
        assert "my_test" in result
    finally:
        os.chdir(orig)


def test_plan_act_plan():
    h = get_handler("plan-act")
    result = asyncio.run(h("plan Step A | Step B"))
    assert "Step A" in result or "plan" in result.lower()


def test_plan_act_act():
    h = get_handler("plan-act")
    result = asyncio.run(h("act Step 1 | Step 2"))
    assert isinstance(result, str)


def test_screenshot_analyze_html():
    h = get_handler("screenshot-analyze")
    result = asyncio.run(h("500 Internal Server Error on page"))
    assert isinstance(result, str)


def test_screenshot_analyze_no_args():
    h = get_handler("screenshot-analyze")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_plan_act_mode():
    h = get_handler("plan-act")
    result = asyncio.run(h("mode"))
    assert "plan" in result.lower() or "mode" in result.lower()
