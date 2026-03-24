"""Tests for learning_cmds (T556)."""
from __future__ import annotations
import asyncio
from unittest.mock import MagicMock
import pytest
from lidco.cli.commands.learning_cmds import register_learning_commands
from lidco.cli.commands.registry import SlashCommand


def make_registry():
    r = MagicMock()
    r.registered = {}
    r.last_message = "async def foo(): pass\n@dataclass\nclass Bar: pass"
    def _register(cmd):
        r.registered[cmd.name] = cmd
    r.register.side_effect = _register
    return r


def get_handler(name):
    r = make_registry()
    register_learning_commands(r)
    return r.registered[name].handler, r


def test_registers_four_commands():
    r = make_registry()
    register_learning_commands(r)
    for name in ("patterns", "apply-review", "workers", "pin-session"):
        assert name in r.registered


def test_patterns_handler_basic():
    h, r = get_handler("patterns")
    result = asyncio.run(h(""))
    assert isinstance(result, str)
    assert len(result) > 0


def test_apply_review_no_args():
    h, _ = get_handler("apply-review")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_apply_review_no_blocks():
    h, _ = get_handler("apply-review")
    result = asyncio.run(h("This is a review with no suggestion blocks."))
    assert "No" in result or "suggestion" in result.lower()


def test_workers_no_args():
    h, _ = get_handler("workers")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_workers_basic():
    h, _ = get_handler("workers")
    result = asyncio.run(h("task1 | task2"))
    assert "ok" in result.lower() or "Pool" in result


def test_pin_session_status(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        h, _ = get_handler("pin-session")
        result = asyncio.run(h("status"))
        assert isinstance(result, str)
    finally:
        os.chdir(orig)


def test_pin_session_pin(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        h, _ = get_handler("pin-session")
        result = asyncio.run(h("pin src/important.py"))
        assert "Pinned" in result or "important" in result
    finally:
        os.chdir(orig)


def test_pin_session_list(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        h, _ = get_handler("pin-session")
        result = asyncio.run(h("list"))
        assert isinstance(result, str)
    finally:
        os.chdir(orig)
