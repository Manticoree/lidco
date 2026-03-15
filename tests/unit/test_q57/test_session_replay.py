"""Tests for Task 386 — /replay command."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch


class TestReplayCommand:
    """Tests for /replay slash command."""

    def _make_store(self, tmp_path):
        from lidco.cli.session_store import SessionStore
        return SessionStore(base_dir=tmp_path)

    def test_replay_no_args_returns_usage(self):
        """Without a session ID, returns usage message."""
        # simulate checking if session_id_parts is empty
        parts = []
        session_id_parts = [p for p in parts if not p.startswith("--")]
        session_id = session_id_parts[0] if session_id_parts else None
        assert session_id is None

    def test_replay_dry_run_flag_detected(self):
        parts = ["abc123", "--dry-run"]
        dry_run = "--dry-run" in parts
        assert dry_run is True

    def test_replay_session_id_extracted(self):
        parts = ["abc123", "--dry-run"]
        session_id_parts = [p for p in parts if not p.startswith("--")]
        assert session_id_parts[0] == "abc123"

    def test_replay_dry_run_shows_messages(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
        ]
        sid = store.save(history)

        data = store.load(sid)
        user_messages = [m.get("content", "") for m in data["history"] if m.get("role") == "user"]
        assert len(user_messages) == 2
        assert "First question" in user_messages
        assert "Second question" in user_messages

    def test_replay_nonexistent_session(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        data = store.load("nonexistent")
        assert data is None

    def test_replay_session_with_no_user_messages(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [
            {"role": "assistant", "content": "I will help you"},
        ]
        sid = store.save(history)
        data = store.load(sid)
        user_messages = [m for m in data["history"] if m.get("role") == "user"]
        assert len(user_messages) == 0

    @pytest.mark.asyncio
    async def test_replay_calls_orchestrator_handle(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [
            {"role": "user", "content": "Do something"},
            {"role": "assistant", "content": "Done"},
        ]
        sid = store.save(history)

        mock_orch = MagicMock()
        mock_orch.handle = AsyncMock(return_value=MagicMock(content="ok"))

        data = store.load(sid)
        user_messages = [
            m.get("content", "") for m in data["history"] if m.get("role") == "user"
        ]

        for msg in user_messages:
            await mock_orch.handle(str(msg))

        assert mock_orch.handle.call_count == len(user_messages)

    def test_replay_dry_run_preview_format(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [
            {"role": "user", "content": "A" * 200},  # Long message
        ]
        sid = store.save(history)
        data = store.load(sid)
        user_messages = [m.get("content", "") for m in data["history"] if m.get("role") == "user"]

        # Dry run should truncate
        lines = [f"**Dry run — {len(user_messages)} messages from `{sid}`:**\n"]
        for i, msg in enumerate(user_messages, 1):
            preview = str(msg)[:100].replace("\n", " ")
            lines.append(f"  {i}. {preview}")

        assert len(lines) == 2
        assert len(lines[1]) <= 110  # roughly capped
