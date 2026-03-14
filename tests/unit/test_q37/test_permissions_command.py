"""Tests for /permissions slash command — Q37 task 248."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lidco.core.config import PermissionsConfig
from lidco.core.permission_engine import PermissionEngine


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_engine(
    mode: str = "default",
    allow_rules: list[str] | None = None,
    deny_rules: list[str] | None = None,
    command_allowlist: list[str] | None = None,
) -> PermissionEngine:
    cfg = PermissionsConfig(
        mode=mode,
        allow_rules=allow_rules or [],
        deny_rules=deny_rules or [],
        command_allowlist=command_allowlist or [],
    )
    return PermissionEngine(cfg)


def _make_registry(engine: PermissionEngine | None = None):
    """Build a minimal mock CommandRegistry with a session that has permission_engine."""
    session = SimpleNamespace(
        permission_engine=engine or _make_engine(),
        project_dir=None,
    )
    registry = MagicMock()
    registry._session = session
    return registry


async def _call_permissions(registry, arg: str = "") -> str:
    """Import and call the real permissions_handler by re-creating CommandRegistry."""
    from lidco.cli.commands import CommandRegistry

    real_registry = CommandRegistry()
    real_registry._session = registry._session
    cmd = real_registry.get("permissions")
    assert cmd is not None, "'/permissions' command not registered"
    return await cmd.handler(arg)


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestPermissionsCommandNoSession:
    def test_returns_error_when_no_session(self) -> None:
        from lidco.cli.commands import CommandRegistry

        registry = CommandRegistry()
        registry._session = None

        async def run():
            cmd = registry.get("permissions")
            return await cmd.handler("")

        result = asyncio.run(run())
        assert "not initialized" in result.lower() or "session" in result.lower()


class TestPermissionsCommandShow:
    def test_shows_mode(self) -> None:
        engine = _make_engine(mode="plan")
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry))
        assert "plan" in result

    def test_shows_default_mode(self) -> None:
        engine = _make_engine(mode="default")
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry))
        assert "default" in result

    def test_shows_allow_rules(self) -> None:
        engine = _make_engine(allow_rules=["FileRead(**)"])
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry))
        assert "FileRead(**)" in result

    def test_shows_deny_rules(self) -> None:
        engine = _make_engine(deny_rules=["Bash(git push *)"])
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry))
        assert "Bash(git push *)" in result

    def test_shows_command_allowlist(self) -> None:
        engine = _make_engine(command_allowlist=["pytest *", "git status"])
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry))
        assert "pytest *" in result or "Bash(pytest *)" in result

    def test_shows_subcommands_hint(self) -> None:
        engine = _make_engine()
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry))
        assert "mode" in result and "add" in result


class TestPermissionsCommandMode:
    def test_set_valid_mode(self) -> None:
        engine = _make_engine(mode="default")
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry, "mode plan"))
        assert "plan" in result
        assert engine.mode.value == "plan"

    def test_set_accept_edits(self) -> None:
        engine = _make_engine()
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry, "mode accept_edits"))
        assert "accept_edits" in result

    def test_set_bypass(self) -> None:
        engine = _make_engine()
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry, "mode bypass"))
        assert "bypass" in result

    def test_invalid_mode_returns_error(self) -> None:
        engine = _make_engine()
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry, "mode nonexistent_mode"))
        assert "invalid" in result.lower() or "valid" in result.lower()

    def test_mode_not_changed_on_invalid(self) -> None:
        engine = _make_engine(mode="default")
        registry = _make_registry(engine)

        asyncio.run(_call_permissions(registry, "mode bad_mode"))
        assert engine.mode.value == "default"


class TestPermissionsCommandAdd:
    def test_add_allow_rule(self) -> None:
        engine = _make_engine()
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry, "add allow Bash(pytest *)"))
        assert "allow" in result.lower()
        # Rule should now be in persistent_allowed
        summary = engine.get_summary()
        assert "Bash(pytest *)" in summary["persistent_allow"]

    def test_add_deny_rule(self) -> None:
        engine = _make_engine()
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry, "add deny Bash(rm -rf *)"))
        assert "deny" in result.lower()
        summary = engine.get_summary()
        assert "Bash(rm -rf *)" in summary["persistent_deny"]

    def test_add_missing_level_returns_usage(self) -> None:
        engine = _make_engine()
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry, "add"))
        # Handler shows usage hint when level/rule not provided
        assert "allow" in result.lower() or "deny" in result.lower() or "usage" in result.lower()

    def test_add_invalid_level_returns_error(self) -> None:
        engine = _make_engine()
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry, "add nope Bash(x)"))
        assert "allow" in result.lower() or "deny" in result.lower()


class TestPermissionsCommandClear:
    def test_clear_session_decisions(self) -> None:
        engine = _make_engine()
        engine.add_session_allow("bash", {"command": "pytest"})
        registry = _make_registry(engine)

        result = asyncio.run(_call_permissions(registry, "clear"))
        assert "clear" in result.lower()
        summary = engine.get_summary()
        assert summary["session_allowed"] == []
