"""Tests for /auto CLI commands (T530)."""
import asyncio
from unittest.mock import MagicMock

import pytest

import lidco.cli.commands.auto_cmds as acmds
from lidco.cli.commands.auto_cmds import (
    auto_list_handler, auto_run_handler, auto_tick_handler,
    auto_enable_handler, auto_disable_handler, register_auto_commands,
)


def run(coro):
    return asyncio.run(coro)


def _make_rule(name="test-rule", trigger="cron", enabled=True):
    r = MagicMock()
    r.name = name
    r.trigger_type = trigger
    r.output_type = "log"
    r.enabled = enabled
    return r


def _make_engine(rules=None):
    e = MagicMock()
    e.rules = rules or []
    result = MagicMock()
    result.success = True
    result.output = "done"
    result.error = ""
    result.rule_name = "test-rule"
    e.run_rule.return_value = result
    e.tick.return_value = []
    return e


# ---- /auto list ----

def test_auto_list_no_engine(monkeypatch):
    acmds._engine = None
    with pytest.MonkeyPatch().context() as m:
        m.setattr(acmds, "_get_engine", lambda: None)
        result = run(auto_list_handler())
    assert "unavailable" in result.lower()


def test_auto_list_no_rules(monkeypatch):
    acmds._engine = _make_engine(rules=[])
    monkeypatch.setattr(acmds, "_get_engine", lambda: acmds._engine)
    result = run(auto_list_handler())
    assert "No automation rules" in result


def test_auto_list_with_rules(monkeypatch):
    rule = _make_rule("backup", "cron")
    acmds._engine = _make_engine(rules=[rule])
    monkeypatch.setattr(acmds, "_get_engine", lambda: acmds._engine)
    result = run(auto_list_handler())
    assert "backup" in result


# ---- /auto run ----

def test_auto_run_no_args(monkeypatch):
    result = run(auto_run_handler(""))
    assert "Usage" in result


def test_auto_run_rule_not_found(monkeypatch):
    acmds._engine = _make_engine(rules=[])
    monkeypatch.setattr(acmds, "_get_engine", lambda: acmds._engine)
    result = run(auto_run_handler("missing"))
    assert "not found" in result


def test_auto_run_success(monkeypatch):
    rule = _make_rule("my-rule")
    acmds._engine = _make_engine(rules=[rule])
    monkeypatch.setattr(acmds, "_get_engine", lambda: acmds._engine)
    result = run(auto_run_handler("my-rule"))
    assert "my-rule" in result


# ---- /auto tick ----

def test_auto_tick_empty(monkeypatch):
    acmds._engine = _make_engine()
    monkeypatch.setattr(acmds, "_get_engine", lambda: acmds._engine)
    result = run(auto_tick_handler())
    assert "No cron rules" in result


def test_auto_tick_with_results(monkeypatch):
    r = MagicMock()
    r.rule_name = "daily"
    r.success = True
    r.error = ""
    engine = _make_engine()
    engine.tick.return_value = [r]
    acmds._engine = engine
    monkeypatch.setattr(acmds, "_get_engine", lambda: acmds._engine)
    result = run(auto_tick_handler())
    assert "daily" in result


# ---- /auto enable / disable ----

def test_auto_enable_no_args():
    result = run(auto_enable_handler(""))
    assert "Usage" in result


def test_auto_enable_success(monkeypatch):
    rule = _make_rule("r", enabled=False)
    acmds._engine = _make_engine(rules=[rule])
    monkeypatch.setattr(acmds, "_get_engine", lambda: acmds._engine)
    result = run(auto_enable_handler("r"))
    assert "enabled" in result


def test_auto_disable_success(monkeypatch):
    rule = _make_rule("r", enabled=True)
    acmds._engine = _make_engine(rules=[rule])
    monkeypatch.setattr(acmds, "_get_engine", lambda: acmds._engine)
    result = run(auto_disable_handler("r"))
    assert "disabled" in result


# ---- registration ----

def test_register_auto_commands():
    registry = MagicMock()
    register_auto_commands(registry)
    assert registry.register.call_count == 5
