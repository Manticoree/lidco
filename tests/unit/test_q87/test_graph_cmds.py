"""Tests for graph_cmds (T571)."""
from __future__ import annotations
import asyncio
from unittest.mock import MagicMock
import pytest
from lidco.cli.commands.graph_cmds import register_graph_commands


def make_registry():
    r = MagicMock()
    r.registered = {}
    def _reg(cmd): r.registered[cmd.name] = cmd
    r.register.side_effect = _reg
    return r


def get_handler(name):
    r = make_registry()
    register_graph_commands(r)
    return r.registered[name].handler


def test_registers_four_commands():
    r = make_registry()
    register_graph_commands(r)
    for name in ("graph", "search", "task-dag", "approve-rules"):
        assert name in r.registered


def test_graph_stats(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "mod.py").write_text("import os\ndef foo(): pass\n")
        h = get_handler("graph")
        result = asyncio.run(h("stats"))
        assert "Dependency Graph" in result or "graph" in result.lower()
    finally:
        os.chdir(orig)


def test_search_no_args():
    h = get_handler("search")
    result = asyncio.run(h(""))
    assert "Usage" in result


def test_search_query(tmp_path):
    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "auth.py").write_text("def login(user): pass\n")
        h = get_handler("search")
        result = asyncio.run(h("login user"))
        assert isinstance(result, str)
    finally:
        os.chdir(orig)


def test_task_dag_plan():
    h = get_handler("task-dag")
    result = asyncio.run(h("plan"))
    assert "Setup" in result or "DAG" in result


def test_task_dag_run():
    h = get_handler("task-dag")
    result = asyncio.run(h("run"))
    assert "done" in result.lower() or "DAG" in result


def test_approve_rules_list():
    h = get_handler("approve-rules")
    result = asyncio.run(h("list"))
    assert "small-safe-change" in result or "docs-only" in result


def test_approve_rules_check_small():
    h = get_handler("approve-rules")
    diff = "+++ b/mod.py\n+x = 1\n"
    result = asyncio.run(h(f"check {diff}"))
    assert "AUTO-APPROVE" in result or "APPROVE" in result or "Verdict" in result
