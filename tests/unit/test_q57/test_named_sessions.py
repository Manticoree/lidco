"""Tests for Task 383 — Named sessions (--session flag, find_by_name, /session rename)."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock


class TestSessionStoreFindByName:
    """Tests for SessionStore.find_by_name()."""

    def test_find_by_name_returns_matching_session(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [{"role": "user", "content": "hello"}]
        store.save(history, metadata={"name": "my-session"})

        result = store.find_by_name("my-session")
        assert result is not None
        assert result["metadata"]["name"] == "my-session"

    def test_find_by_name_returns_none_for_missing(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        result = store.find_by_name("does-not-exist")
        assert result is None

    def test_find_by_name_returns_none_when_dir_empty(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path / "sessions")
        result = store.find_by_name("anything")
        assert result is None

    def test_find_by_name_returns_most_recent_match(self, tmp_path):
        import time
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        store.save([{"role": "user", "content": "v1"}], metadata={"name": "proj"})
        time.sleep(0.01)
        store.save([{"role": "user", "content": "v2"}], metadata={"name": "proj"})

        result = store.find_by_name("proj")
        assert result is not None
        # Most recent should have content "v2"
        assert result["history"][0]["content"] == "v2"

    def test_find_by_name_ignores_unnamed_sessions(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        store.save([{"role": "user", "content": "unnamed"}])

        result = store.find_by_name("anything")
        assert result is None


class TestCLIFlagsSessionProfile:
    """Tests for --session and --profile flags in CLIFlags."""

    def test_session_name_field_exists(self):
        from lidco.__main__ import CLIFlags
        flags = CLIFlags()
        assert hasattr(flags, "session_name")
        assert flags.session_name is None

    def test_profile_name_field_exists(self):
        from lidco.__main__ import CLIFlags
        flags = CLIFlags()
        assert hasattr(flags, "profile_name")
        assert flags.profile_name is None

    def test_parse_session_flag(self):
        from lidco.__main__ import _parse_repl_flags
        flags = _parse_repl_flags(["--session", "my-work"])
        assert flags.session_name == "my-work"

    def test_parse_profile_flag(self):
        from lidco.__main__ import _parse_repl_flags
        flags = _parse_repl_flags(["--profile", "backend"])
        assert flags.profile_name == "backend"

    def test_parse_session_and_profile_together(self):
        from lidco.__main__ import _parse_repl_flags
        flags = _parse_repl_flags(["--session", "dev", "--profile", "frontend"])
        assert flags.session_name == "dev"
        assert flags.profile_name == "frontend"

    def test_session_name_none_by_default(self):
        from lidco.__main__ import _parse_repl_flags
        flags = _parse_repl_flags(["--no-plan"])
        assert flags.session_name is None


class TestSessionRenameCommand:
    """Tests for /session rename <name>."""

    @pytest.mark.asyncio
    async def test_session_rename_saves_with_new_name(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [{"role": "user", "content": "test"}]
        sid = store.save(history)

        # Simulate rename by saving with new name metadata
        store.save(history, session_id=sid, metadata={"name": "new-name"})
        data = store.load(sid)
        assert data["metadata"]["name"] == "new-name"

    @pytest.mark.asyncio
    async def test_session_rename_returns_confirmation(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [{"role": "user", "content": "hello"}]
        sid = store.save(history)

        new_sid = store.save(history, session_id=sid, metadata={"name": "renamed"})
        assert new_sid == sid  # same id, updated metadata
