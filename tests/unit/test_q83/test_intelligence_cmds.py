"""Tests for intelligence_cmds (T546)."""
from __future__ import annotations
import asyncio
from unittest.mock import MagicMock
import pytest
from lidco.cli.commands.intelligence_cmds import register_intelligence_commands
from lidco.cli.commands.registry import SlashCommand


def make_registry():
    r = MagicMock()
    r.registered = {}
    def _register(cmd):
        r.registered[cmd.name] = cmd
    r.register.side_effect = _register
    return r


def get_handler(name):
    r = make_registry()
    register_intelligence_commands(r)
    return r.registered[name].handler


def test_registers_four_commands():
    r = make_registry()
    register_intelligence_commands(r)
    # /index renamed to /deep-index to avoid overriding core.py's IndexDatabase /index
    for name in ("deep-index", "plan-validate", "autofix", "parallel"):
        assert name in r.registered


def test_index_handler_basic(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "mod.py").write_text("def foo(): pass\n")
        h = get_handler("deep-index")
        result = asyncio.run(h(""))
        assert "files" in result.lower() or "Codebase" in result
    finally:
        os.chdir(orig)


def test_plan_validate_no_args():
    h = get_handler("plan-validate")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_plan_validate_with_steps():
    h = get_handler("plan-validate")
    result = asyncio.run(h("1. Do first\n2. Do second"))
    assert "Plan" in result or "Approved" in result


def test_autofix_no_args():
    h = get_handler("autofix")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_autofix_passing_command():
    import sys
    h = get_handler("autofix")
    result = asyncio.run(h(f"{sys.executable} -c \"print('ok')\""))
    assert "PASSED" in result


def test_autofix_failing_command():
    import sys
    h = get_handler("autofix")
    result = asyncio.run(h(f"{sys.executable} -c \"import sys; sys.exit(1)\""))
    assert "FAILED" in result


def test_parallel_no_args():
    h = get_handler("parallel")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_parallel_runs_tasks(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        h = get_handler("parallel")
        result = asyncio.run(h("task1 | task2"))
        assert "parallel" in result.lower() or "task" in result.lower()
    finally:
        os.chdir(orig)
