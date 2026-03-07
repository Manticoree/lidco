"""Tests for /as, /lock, /unlock commands — Task 152."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_registry(agents: list[str] | None = None) -> CommandRegistry:
    registry = CommandRegistry()
    if agents is not None:
        session = MagicMock()
        session.agent_registry.list_names.return_value = agents
        registry.set_session(session)
    return registry


def _run(coro) -> str:
    return asyncio.run(coro)


# ── /as command ───────────────────────────────────────────────────────────────

class TestAsCommand:
    def test_valid_returns_retry_sentinel(self) -> None:
        reg = _make_registry(["coder", "debugger"])
        cmd = reg.get("as")
        result = _run(cmd.handler(arg="coder fix the bug"))
        assert result == "__RETRY__:@coder fix the bug"

    def test_agent_and_message_preserved(self) -> None:
        reg = _make_registry(["architect"])
        cmd = reg.get("as")
        result = _run(cmd.handler(arg="architect review this design carefully"))
        assert result == "__RETRY__:@architect review this design carefully"

    def test_message_with_multiple_words(self) -> None:
        reg = _make_registry(["coder"])
        cmd = reg.get("as")
        result = _run(cmd.handler(arg="coder fix   auth.py login bug"))
        assert result.startswith("__RETRY__:@coder")
        assert "fix" in result

    def test_no_args_returns_usage(self) -> None:
        reg = _make_registry(["coder"])
        cmd = reg.get("as")
        result = _run(cmd.handler(arg=""))
        assert "Использование" in result or "as" in result.lower()
        assert "__RETRY__" not in result

    def test_only_agent_no_message_returns_usage(self) -> None:
        reg = _make_registry(["coder"])
        cmd = reg.get("as")
        result = _run(cmd.handler(arg="coder"))
        assert "__RETRY__" not in result
        assert "Использование" in result or "Пример" in result

    def test_unknown_agent_returns_error(self) -> None:
        reg = _make_registry(["coder", "debugger"])
        cmd = reg.get("as")
        result = _run(cmd.handler(arg="ghost fix something"))
        assert "__RETRY__" not in result
        assert "ghost" in result or "не найден" in result

    def test_no_session_skips_validation(self) -> None:
        reg = CommandRegistry()  # no session
        cmd = reg.get("as")
        result = _run(cmd.handler(arg="anyone do something"))
        # Without session we can't validate — should still produce retry
        assert result == "__RETRY__:@anyone do something"

    def test_lists_available_agents_in_usage(self) -> None:
        reg = _make_registry(["coder", "tester"])
        cmd = reg.get("as")
        result = _run(cmd.handler(arg=""))
        assert "coder" in result
        assert "tester" in result


# ── /lock command ─────────────────────────────────────────────────────────────

class TestLockCommand:
    def test_lock_valid_agent(self) -> None:
        reg = _make_registry(["coder", "debugger"])
        cmd = reg.get("lock")
        _run(cmd.handler(arg="coder"))
        assert reg.locked_agent == "coder"

    def test_lock_returns_confirmation(self) -> None:
        reg = _make_registry(["coder"])
        cmd = reg.get("lock")
        result = _run(cmd.handler(arg="coder"))
        assert "coder" in result
        assert "закреплён" in result

    def test_lock_unknown_agent_returns_error(self) -> None:
        reg = _make_registry(["coder"])
        cmd = reg.get("lock")
        result = _run(cmd.handler(arg="phantom"))
        assert reg.locked_agent is None
        assert "phantom" in result or "не найден" in result

    def test_lock_off_clears_locked_agent(self) -> None:
        reg = _make_registry(["coder"])
        reg.locked_agent = "coder"
        cmd = reg.get("lock")
        _run(cmd.handler(arg="off"))
        assert reg.locked_agent is None

    def test_lock_off_aliases(self) -> None:
        for alias in ("off", "clear", "none", "auto"):
            reg = _make_registry(["coder"])
            reg.locked_agent = "coder"
            cmd = reg.get("lock")
            _run(cmd.handler(arg=alias))
            assert reg.locked_agent is None, f"alias '{alias}' did not clear lock"

    def test_lock_no_arg_shows_current(self) -> None:
        reg = _make_registry(["coder"])
        reg.locked_agent = "coder"
        cmd = reg.get("lock")
        result = _run(cmd.handler(arg=""))
        assert "coder" in result

    def test_lock_no_arg_no_lock_shows_status(self) -> None:
        reg = _make_registry(["coder"])
        cmd = reg.get("lock")
        result = _run(cmd.handler(arg=""))
        assert "не закреплён" in result or "авторотация" in result

    def test_lock_no_session_skips_validation(self) -> None:
        reg = CommandRegistry()  # no session
        cmd = reg.get("lock")
        _run(cmd.handler(arg="any_agent"))
        assert reg.locked_agent == "any_agent"

    def test_lock_overwrite(self) -> None:
        reg = _make_registry(["coder", "tester"])
        reg.locked_agent = "coder"
        cmd = reg.get("lock")
        _run(cmd.handler(arg="tester"))
        assert reg.locked_agent == "tester"


# ── /unlock command ───────────────────────────────────────────────────────────

class TestUnlockCommand:
    def test_unlock_clears_locked_agent(self) -> None:
        reg = _make_registry(["coder"])
        reg.locked_agent = "coder"
        cmd = reg.get("unlock")
        _run(cmd.handler())
        assert reg.locked_agent is None

    def test_unlock_returns_confirmation_with_agent_name(self) -> None:
        reg = _make_registry(["coder"])
        reg.locked_agent = "coder"
        cmd = reg.get("unlock")
        result = _run(cmd.handler())
        assert "coder" in result

    def test_unlock_when_not_locked(self) -> None:
        reg = CommandRegistry()
        cmd = reg.get("unlock")
        result = _run(cmd.handler())
        assert "не был закреплён" in result or "не" in result

    def test_unlock_leaves_none(self) -> None:
        reg = CommandRegistry()
        reg.locked_agent = None
        cmd = reg.get("unlock")
        _run(cmd.handler())
        assert reg.locked_agent is None


# ── locked_agent initial state ────────────────────────────────────────────────

class TestLockedAgentDefault:
    def test_initial_value_is_none(self) -> None:
        reg = CommandRegistry()
        assert reg.locked_agent is None

    def test_commands_registered(self) -> None:
        reg = CommandRegistry()
        assert reg.get("as") is not None
        assert reg.get("lock") is not None
        assert reg.get("unlock") is not None
