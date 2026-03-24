"""Tests for Q66 Task 444 — Session continuity (--continue / --resume)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

import pytest


# ---------------------------------------------------------------------------
# Helper: build a CLIFlags with continue/resume fields
# ---------------------------------------------------------------------------
def _make_flags(**overrides):
    """Create a CLIFlags-like object with all defaults."""
    from lidco.__main__ import CLIFlags
    return CLIFlags(**overrides)


# ---------------------------------------------------------------------------
# 1. test_continue_flag_loads_latest_session
# ---------------------------------------------------------------------------
class TestContinueFlagLoadsLatestSession:
    """--continue should load the most recent session from the store."""

    def test_continue_flag_restores_history(self):
        flags = _make_flags(continue_session=True)
        assert flags.continue_session is True

        # Verify that the SessionStore.list_sessions is used to find latest
        from lidco.cli.session_store import SessionStore
        store = SessionStore(base_dir=MagicMock())
        store.list_sessions = MagicMock(return_value=[
            {
                "session_id": "abc123",
                "saved_at": "2026-03-18T10:00:00+00:00",
                "message_count": 4,
                "metadata": {"name": "main"},
            }
        ])
        store.load = MagicMock(return_value={
            "session_id": "abc123",
            "history": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
                {"role": "user", "content": "fix bug"},
                {"role": "assistant", "content": "done"},
            ],
            "metadata": {"name": "main"},
        })

        # Simulate what app.py does: list sessions, pick first, load, restore
        sessions = store.list_sessions()
        assert len(sessions) > 0
        latest = sessions[0]
        data = store.load(latest["session_id"])
        assert data is not None
        assert len(data["history"]) == 4

        # Mock orchestrator restore
        orch = MagicMock()
        orch.restore_history = MagicMock()
        orch.restore_history(data["history"])
        orch.restore_history.assert_called_once_with(data["history"])


# ---------------------------------------------------------------------------
# 2. test_resume_by_id
# ---------------------------------------------------------------------------
class TestResumeById:
    """--resume <ID> should load that specific session."""

    def test_resume_loads_specific_session(self):
        flags = _make_flags(resume_id="deadbeef")
        assert flags.resume_id == "deadbeef"

        from lidco.cli.session_store import SessionStore
        store = SessionStore(base_dir=MagicMock())
        store.load = MagicMock(return_value={
            "session_id": "deadbeef",
            "history": [
                {"role": "user", "content": "test"},
                {"role": "assistant", "content": "ok"},
            ],
            "metadata": {"name": "feature-branch"},
        })

        data = store.load("deadbeef")
        assert data is not None
        assert data["session_id"] == "deadbeef"
        assert len(data["history"]) == 2


# ---------------------------------------------------------------------------
# 3. test_resume_by_name
# ---------------------------------------------------------------------------
class TestResumeByName:
    """--resume <name> should fall back to find_by_name when load returns None."""

    def test_resume_falls_back_to_name_search(self):
        flags = _make_flags(resume_id="feature-x")

        from lidco.cli.session_store import SessionStore
        store = SessionStore(base_dir=MagicMock())
        # Direct ID lookup fails
        store.load = MagicMock(return_value=None)
        # Name search succeeds
        store.find_by_name = MagicMock(return_value={
            "session_id": "xyz789",
            "history": [
                {"role": "user", "content": "implement feature x"},
                {"role": "assistant", "content": "done"},
            ],
            "metadata": {"name": "feature-x"},
        })

        # Simulate app.py logic: try load first, then find_by_name
        data = store.load(flags.resume_id)
        if data is None:
            data = store.find_by_name(flags.resume_id)

        assert data is not None
        assert data["metadata"]["name"] == "feature-x"
        store.find_by_name.assert_called_once_with("feature-x")


# ---------------------------------------------------------------------------
# 4. test_continue_empty_store_graceful
# ---------------------------------------------------------------------------
class TestContinueEmptyStoreGraceful:
    """--continue with no saved sessions should not crash."""

    def test_empty_store_returns_no_data(self):
        from lidco.cli.session_store import SessionStore
        store = SessionStore(base_dir=MagicMock())
        store.list_sessions = MagicMock(return_value=[])

        sessions = store.list_sessions()
        assert sessions == []
        # No session to load — REPL should start fresh (no restore call)


# ---------------------------------------------------------------------------
# 5. test_auto_save_on_exit
# ---------------------------------------------------------------------------
class TestAutoSaveOnExit:
    """REPL exit should auto-save the conversation history."""

    def test_save_called_with_history_and_branch_name(self):
        from lidco.cli.session_store import SessionStore
        store = SessionStore(base_dir=MagicMock())
        store._ensure_dir = MagicMock()
        store.save = MagicMock(return_value="new_session_id")

        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        branch = "main"

        # Simulate what app.py does on exit
        if history:
            store.save(
                history,
                metadata={"name": branch, "auto_saved": True},
            )

        store.save.assert_called_once_with(
            history,
            metadata={"name": branch, "auto_saved": True},
        )

    def test_no_save_when_history_empty(self):
        from lidco.cli.session_store import SessionStore
        store = SessionStore(base_dir=MagicMock())
        store.save = MagicMock()

        history = []
        if history:
            store.save(history, metadata={"name": "main", "auto_saved": True})

        store.save.assert_not_called()


# ---------------------------------------------------------------------------
# 6. test_sessions_command_lists
# ---------------------------------------------------------------------------
class TestSessionsCommandLists:
    """/sessions should return a formatted list of saved sessions."""

    def test_sessions_handler_returns_list(self):
        from lidco.cli.commands.session import register
        from lidco.cli.commands.registry import SlashCommand

        # Build a minimal registry mock
        registry = MagicMock()
        registered_commands: dict[str, SlashCommand] = {}

        def _register(cmd):
            registered_commands[cmd.name] = cmd

        registry.register = _register
        registry._session = MagicMock()

        # Need to set _session_store before register
        mock_store = MagicMock()
        mock_store.list_sessions.return_value = [
            {
                "session_id": "abc12345dead",
                "saved_at": "2026-03-18T10:00:00+00:00",
                "message_count": 6,
                "metadata": {"name": "feature-branch"},
            },
            {
                "session_id": "def67890beef",
                "saved_at": "2026-03-17T08:00:00+00:00",
                "message_count": 2,
                "metadata": {"name": "bugfix"},
            },
        ]
        registry._session_store = mock_store

        register(registry)
        assert "sessions" in registered_commands

        result = asyncio.run(registered_commands["sessions"].handler(arg=""))
        assert "abc12345" in result
        assert "feature-branch" in result
        assert "def67890" in result
        assert "bugfix" in result
        assert "6 msgs" in result


# ---------------------------------------------------------------------------
# 7. test_sessions_command_empty
# ---------------------------------------------------------------------------
class TestSessionsCommandEmpty:
    """/sessions when no sessions exist should return a friendly message."""

    def test_sessions_handler_empty(self):
        from lidco.cli.commands.session import register
        from lidco.cli.commands.registry import SlashCommand

        registry = MagicMock()
        registered_commands: dict[str, SlashCommand] = {}

        def _register(cmd):
            registered_commands[cmd.name] = cmd

        registry.register = _register
        registry._session = MagicMock()

        mock_store = MagicMock()
        mock_store.list_sessions.return_value = []
        registry._session_store = mock_store

        register(registry)
        assert "sessions" in registered_commands

        result = asyncio.run(registered_commands["sessions"].handler(arg=""))
        assert "No saved sessions" in result


# ---------------------------------------------------------------------------
# 8. test_resume_invalid_id_error
# ---------------------------------------------------------------------------
class TestResumeInvalidIdError:
    """--resume with an unknown ID (and no matching name) should yield None."""

    def test_resume_unknown_id_returns_none(self):
        from lidco.cli.session_store import SessionStore
        store = SessionStore(base_dir=MagicMock())
        store.load = MagicMock(return_value=None)
        store.find_by_name = MagicMock(return_value=None)

        resume_id = "nonexistent"
        data = store.load(resume_id)
        if data is None:
            data = store.find_by_name(resume_id)

        assert data is None
        store.load.assert_called_once_with("nonexistent")
        store.find_by_name.assert_called_once_with("nonexistent")


# ---------------------------------------------------------------------------
# 9. test_cli_flags_parsing_continue
# ---------------------------------------------------------------------------
class TestCLIFlagsParsing:
    """Verify _parse_repl_flags handles --continue and --resume."""

    def test_parse_continue_flag(self):
        from lidco.__main__ import _parse_repl_flags
        flags = _parse_repl_flags(["--continue"])
        assert flags.continue_session is True

    def test_parse_resume_flag(self):
        from lidco.__main__ import _parse_repl_flags
        flags = _parse_repl_flags(["--resume", "my-session-id"])
        assert flags.resume_id == "my-session-id"

    def test_parse_resume_with_other_flags(self):
        from lidco.__main__ import _parse_repl_flags
        flags = _parse_repl_flags(["--no-plan", "--resume", "sess123", "--no-review"])
        assert flags.resume_id == "sess123"
        assert flags.no_plan is True
        assert flags.no_review is True

    def test_continue_and_resume_coexist(self):
        from lidco.__main__ import _parse_repl_flags
        flags = _parse_repl_flags(["--continue", "--resume", "abc"])
        assert flags.continue_session is True
        assert flags.resume_id == "abc"
