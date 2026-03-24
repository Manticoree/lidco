"""Tests for standards slash commands (T516)."""
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import lidco.cli.commands.standards_cmds as scmds
from lidco.cli.commands.standards_cmds import (
    standards_check_handler,
    standards_rules_handler,
    standards_add_handler,
    standards_init_handler,
    pre_commit_check,
    register_standards_commands,
)


def run(coro):
    return asyncio.run(coro)


def _make_enforcer(rules=None, violations=None):
    enforcer = MagicMock()
    enforcer.list_rules.return_value = rules or []
    enforcer.check_diff.return_value = violations or []
    enforcer.load_yaml.return_value = 3
    return enforcer


# ---- /standards check ----

def test_standards_check_no_staged_files():
    with patch("lidco.cli.commands.standards_cmds.pre_commit_check", return_value=""):
        result = run(standards_check_handler())
    assert "passed" in result


def test_standards_check_with_violations():
    with patch("lidco.cli.commands.standards_cmds.pre_commit_check", return_value="foo.py:1 [ERROR] rule1: bad code"):
        result = run(standards_check_handler())
    assert "violations" in result


# ---- /standards rules ----

def test_standards_rules_no_enforcer(monkeypatch):
    monkeypatch.setattr(scmds, "_enforcer", None)
    with patch("lidco.cli.commands.standards_cmds._get_enforcer", return_value=None):
        result = run(standards_rules_handler())
    assert "unavailable" in result.lower()


def test_standards_rules_no_rules(monkeypatch):
    enforcer = _make_enforcer(rules=[])
    monkeypatch.setattr(scmds, "_enforcer", enforcer)
    with patch("lidco.cli.commands.standards_cmds._get_enforcer", return_value=enforcer):
        result = run(standards_rules_handler())
    assert "No rules" in result


def test_standards_rules_with_rules(monkeypatch):
    rule = MagicMock()
    rule.id = "R1"
    rule.name = "No TODO"
    rule.severity = "error"
    enforcer = _make_enforcer(rules=[rule])
    monkeypatch.setattr(scmds, "_enforcer", enforcer)
    with patch("lidco.cli.commands.standards_cmds._get_enforcer", return_value=enforcer):
        result = run(standards_rules_handler())
    assert "R1" in result
    assert "No TODO" in result


# ---- /standards add ----

def test_standards_add_no_args(monkeypatch):
    enforcer = _make_enforcer()
    monkeypatch.setattr(scmds, "_enforcer", enforcer)
    with patch("lidco.cli.commands.standards_cmds._get_enforcer", return_value=enforcer):
        result = run(standards_add_handler(""))
    assert "Usage" in result


def test_standards_add_valid_path(monkeypatch):
    enforcer = _make_enforcer()
    monkeypatch.setattr(scmds, "_enforcer", enforcer)
    with patch("lidco.cli.commands.standards_cmds._get_enforcer", return_value=enforcer):
        result = run(standards_add_handler("rules.yaml"))
    assert "3 rule" in result


# ---- /standards init ----

def test_standards_init_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("lidco.standards.enforcer.StandardsEnforcer") as cls:
        cls.default_yaml_content.return_value = "rules: []"
        result = run(standards_init_handler())
    assert "Created" in result


def test_standards_init_handles_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("lidco.standards.enforcer.StandardsEnforcer") as cls:
        cls.default_yaml_content.side_effect = RuntimeError("boom")
        result = run(standards_init_handler())
    assert "Failed" in result or "failed" in result


# ---- pre_commit_check ----

def test_pre_commit_check_no_staged(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        result = pre_commit_check(tmp_path)
    assert result == ""


def test_pre_commit_check_returns_empty_if_enforcer_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(scmds, "_enforcer", None)
    with patch("subprocess.run") as mock_run, \
         patch("lidco.cli.commands.standards_cmds._get_enforcer", return_value=None):
        mock_run.return_value = MagicMock(stdout="file.py\n", returncode=0)
        result = pre_commit_check(tmp_path)
    assert result == ""


# ---- register ----

def test_register_standards_commands():
    registry = MagicMock()
    register_standards_commands(registry)
    assert registry.register.call_count >= 4
