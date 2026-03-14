"""Tests for PermissionManager — Q37 refactored API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lidco.cli.approval import Decision
from lidco.cli.permissions import PermissionManager
from lidco.core.config import PermissionsConfig
from lidco.core.permission_engine import PermissionEngine, PermissionMode


def _make_manager(
    mode: str = "default",
    allow_rules: list[str] | None = None,
    deny_rules: list[str] | None = None,
    command_allowlist: list[str] | None = None,
) -> PermissionManager:
    config = PermissionsConfig(
        mode=mode,
        allow_rules=allow_rules or [],
        deny_rules=deny_rules or [],
        command_allowlist=command_allowlist or [],
    )
    console = MagicMock()
    return PermissionManager(config, console)


# ─── Basic allow/deny decisions ───────────────────────────────────────────────


class TestPermissionManagerCheck:
    def test_allowed_tool_returns_true(self) -> None:
        mgr = _make_manager(allow_rules=["FileRead(**)"])
        result = mgr.check("file_read", {"path": "foo.py"})
        assert result is True

    def test_denied_tool_returns_false(self) -> None:
        mgr = _make_manager(deny_rules=["Bash(rm -rf *)"])
        result = mgr.check("bash", {"command": "rm -rf /tmp/x"})
        assert result is False

    def test_ask_decision_calls_approval(self) -> None:
        mgr = _make_manager()
        with patch("lidco.cli.permissions.ask", return_value=Decision.ALLOW_ONCE) as mock_ask:
            result = mgr.check("bash", {"command": "echo hi"})
        mock_ask.assert_called_once()
        assert result is True

    def test_deny_once_returns_false(self) -> None:
        mgr = _make_manager()
        with patch("lidco.cli.permissions.ask", return_value=Decision.DENY_ONCE):
            result = mgr.check("bash", {"command": "echo hi"})
        assert result is False

    def test_deny_always_returns_false(self) -> None:
        mgr = _make_manager()
        with patch("lidco.cli.permissions.ask", return_value=Decision.DENY_ALWAYS):
            result = mgr.check("bash", {"command": "echo hi"})
        assert result is False

    def test_read_only_tools_auto_allowed(self) -> None:
        mgr = _make_manager()
        for tool in ("file_read", "glob", "grep"):
            assert mgr.check(tool, {}) is True, f"{tool} should be auto-allowed"


# ─── Session allow ────────────────────────────────────────────────────────────


class TestAllowSession:
    def test_allow_session_adds_to_session_list(self) -> None:
        mgr = _make_manager()
        with patch("lidco.cli.permissions.ask", return_value=Decision.ALLOW_SESSION):
            mgr.check("bash", {"command": "pytest -q tests/"})
        summary = mgr.engine.get_summary()
        assert len(summary["session_allowed"]) == 1

    def test_session_allowed_tool_skips_prompt_second_time(self) -> None:
        mgr = _make_manager()
        with patch("lidco.cli.permissions.ask", return_value=Decision.ALLOW_SESSION):
            mgr.check("bash", {"command": "pytest -q tests/"})
        # Second call with same prefix should be auto-allowed without asking
        with patch("lidco.cli.permissions.ask") as mock_ask:
            result = mgr.check("bash", {"command": "pytest -x unit/"})
        mock_ask.assert_not_called()
        assert result is True


# ─── Persistent allow/deny ───────────────────────────────────────────────────


class TestPersistentDecisions:
    def test_allow_always_saves_persistent_rule(self) -> None:
        mgr = _make_manager()
        with patch("lidco.cli.permissions.ask", return_value=Decision.ALLOW_ALWAYS):
            mgr.check("bash", {"command": "pytest -q"})
        summary = mgr.engine.get_summary()
        assert len(summary["persistent_allow"]) == 1

    def test_deny_always_saves_persistent_deny(self) -> None:
        mgr = _make_manager()
        with patch("lidco.cli.permissions.ask", return_value=Decision.DENY_ALWAYS):
            mgr.check("bash", {"command": "rm -rf /tmp"})
        summary = mgr.engine.get_summary()
        assert len(summary["persistent_deny"]) == 1


# ─── Backward compat methods ─────────────────────────────────────────────────


class TestBackwardCompat:
    def test_auto_allow_marks_tool_as_session_allowed(self) -> None:
        mgr = _make_manager()
        mgr.auto_allow("file_write")
        with patch("lidco.cli.permissions.ask") as mock_ask:
            result = mgr.check("file_write", {"path": "foo.py"})
        mock_ask.assert_not_called()
        assert result is True

    def test_allow_all_sets_bypass_mode(self) -> None:
        mgr = _make_manager()
        mgr.allow_all()
        assert mgr.engine.mode == PermissionMode.BYPASS

    def test_bypass_mode_allows_everything_without_prompt(self) -> None:
        mgr = _make_manager()
        mgr.allow_all()
        with patch("lidco.cli.permissions.ask") as mock_ask:
            result = mgr.check("bash", {"command": "rm -rf /tmp/test"})
        mock_ask.assert_not_called()
        assert result is True

    def test_engine_property(self) -> None:
        mgr = _make_manager()
        assert isinstance(mgr.engine, PermissionEngine)


# ─── Permission modes ─────────────────────────────────────────────────────────


class TestPermissionModes:
    def test_plan_mode_denies_bash(self) -> None:
        mgr = _make_manager(mode="plan")
        result = mgr.check("bash", {"command": "echo hi"})
        assert result is False

    def test_plan_mode_denies_file_write(self) -> None:
        mgr = _make_manager(mode="plan")
        result = mgr.check("file_write", {"path": "foo.py"})
        assert result is False

    def test_plan_mode_allows_reads(self) -> None:
        mgr = _make_manager(mode="plan")
        assert mgr.check("file_read", {"path": "foo.py"}) is True
        assert mgr.check("grep", {}) is True

    def test_accept_edits_auto_allows_file_write(self) -> None:
        mgr = _make_manager(mode="accept_edits")
        with patch("lidco.cli.permissions.ask") as mock_ask:
            result = mgr.check("file_write", {"path": "foo.py"})
        mock_ask.assert_not_called()
        assert result is True


# ─── Command allowlist integration ───────────────────────────────────────────


class TestCommandAllowlistIntegration:
    def test_allowlisted_command_skips_prompt(self) -> None:
        mgr = _make_manager(command_allowlist=["pytest *"])
        with patch("lidco.cli.permissions.ask") as mock_ask:
            result = mgr.check("bash", {"command": "pytest -q tests/"})
        mock_ask.assert_not_called()
        assert result is True

    def test_non_allowlisted_command_prompts(self) -> None:
        mgr = _make_manager(command_allowlist=["pytest *"])
        with patch("lidco.cli.permissions.ask", return_value=Decision.ALLOW_ONCE):
            result = mgr.check("bash", {"command": "curl https://example.com"})
        assert result is True  # asked and allowed

    def test_deny_rule_overrides_allowlist(self) -> None:
        mgr = _make_manager(
            command_allowlist=["pytest *"],
            deny_rules=["Bash(pytest *)"],
        )
        result = mgr.check("bash", {"command": "pytest tests/"})
        assert result is False
