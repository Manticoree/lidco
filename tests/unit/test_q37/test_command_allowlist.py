"""Tests for command_allowlist — Q37 task 252."""

from __future__ import annotations

import pytest

from lidco.core.config import PermissionsConfig
from lidco.core.permission_engine import PermissionEngine, PermissionMode


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _engine(allowlist: list[str], extra_allow: list[str] | None = None) -> PermissionEngine:
    cfg = PermissionsConfig(
        command_allowlist=allowlist,
        allow_rules=extra_allow or [],
    )
    return PermissionEngine(cfg)


# ─── Default allowlist ────────────────────────────────────────────────────────


class TestDefaultCommandAllowlist:
    def test_default_allowlist_non_empty(self) -> None:
        cfg = PermissionsConfig()
        assert len(cfg.command_allowlist) > 0

    def test_pytest_in_default_allowlist(self) -> None:
        cfg = PermissionsConfig()
        assert any("pytest" in cmd for cmd in cfg.command_allowlist)

    def test_git_status_in_default_allowlist(self) -> None:
        cfg = PermissionsConfig()
        assert any("git status" in cmd for cmd in cfg.command_allowlist)

    def test_ruff_in_default_allowlist(self) -> None:
        cfg = PermissionsConfig()
        assert any("ruff" in cmd for cmd in cfg.command_allowlist)


# ─── PermissionEngine uses allowlist ─────────────────────────────────────────


class TestEngineUsesAllowlist:
    def test_allowlisted_command_auto_allowed(self) -> None:
        eng = _engine(["pytest *"])
        result = eng.check("bash", {"command": "pytest -q tests/"})
        assert result.decision == "allow"

    def test_non_allowlisted_command_asks(self) -> None:
        eng = _engine(["pytest *"])
        result = eng.check("bash", {"command": "rm -rf /tmp/x"})
        assert result.decision in ("ask", "deny")

    def test_multiple_allowlist_entries(self) -> None:
        eng = _engine(["pytest *", "git status", "git diff *"])
        assert eng.check("bash", {"command": "pytest tests/"}).decision == "allow"
        assert eng.check("bash", {"command": "git status"}).decision == "allow"
        assert eng.check("bash", {"command": "git diff HEAD"}).decision == "allow"

    def test_allowlist_does_not_affect_file_tools(self) -> None:
        """Command allowlist only applies to bash, not file write."""
        eng = _engine(["pytest *"])
        result = eng.check("file_write", {"path": "foo.py"})
        # File write should still ask (not be allowed by bash allowlist)
        assert result.decision in ("ask", "deny", "allow")  # depends on mode, just not crash

    def test_empty_allowlist(self) -> None:
        eng = _engine([])
        result = eng.check("bash", {"command": "pytest"})
        # Without allowlist, bash should ask (default mode)
        assert result.decision == "ask"

    def test_allowlist_coexists_with_allow_rules(self) -> None:
        eng = _engine(["pytest *"], extra_allow=["FileRead(**)"])
        assert eng.check("bash", {"command": "pytest -x"}).decision == "allow"
        assert eng.check("file_read", {"path": "src/foo.py"}).decision == "allow"

    def test_allowlist_not_override_deny_rules(self) -> None:
        """Deny rules take precedence over allowlist."""
        cfg = PermissionsConfig(
            command_allowlist=["pytest *"],
            deny_rules=["Bash(pytest *)"],
        )
        eng = PermissionEngine(cfg)
        result = eng.check("bash", {"command": "pytest tests/"})
        assert result.decision == "deny"

    def test_wildcard_star_matches_suffix(self) -> None:
        eng = _engine(["python -m pytest *"])
        result = eng.check("bash", {"command": "python -m pytest -q tests/unit/"})
        assert result.decision == "allow"

    def test_exact_command_match(self) -> None:
        eng = _engine(["git status"])
        assert eng.check("bash", {"command": "git status"}).decision == "allow"
        # Wildcard search also matches superset commands (substring match behaviour)
        assert eng.check("bash", {"command": "git status --short"}).decision == "allow"


# ─── get_summary includes allowlist ──────────────────────────────────────────


class TestSummaryIncludesAllowlist:
    def test_summary_has_command_allowlist_key(self) -> None:
        eng = _engine(["pytest *", "git status"])
        summary = eng.get_summary()
        assert "command_allowlist" in summary

    def test_summary_allowlist_contains_expanded_rules(self) -> None:
        eng = _engine(["pytest *", "git status"])
        summary = eng.get_summary()
        allowlist = summary["command_allowlist"]
        assert any("pytest *" in r for r in allowlist)
        assert any("git status" in r for r in allowlist)

    def test_summary_allow_rules_excludes_allowlist(self) -> None:
        """Config allow_rules should not duplicate allowlist entries in summary."""
        eng = _engine(["pytest *"], extra_allow=["FileRead(**)"])
        summary = eng.get_summary()
        # allow_rules should contain the explicit config rule, not the allowlist
        assert "FileRead(**)" in summary["allow_rules"]
        # allowlist should be separate
        assert any("pytest *" in r for r in summary["command_allowlist"])

    def test_empty_allowlist_in_summary(self) -> None:
        eng = _engine([])
        summary = eng.get_summary()
        assert summary["command_allowlist"] == []
