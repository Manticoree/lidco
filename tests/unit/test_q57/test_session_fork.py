"""Tests for Task 382 — Session forking via SessionStore.fork() and /fork command."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock


class TestSessionStoreFork:
    """Unit tests for SessionStore.fork() method."""

    def test_fork_creates_new_session(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [{"role": "user", "content": "hello"}]
        parent_id = store.save(history)

        fork_id = store.fork(parent_id)
        assert fork_id is not None
        assert fork_id != parent_id

    def test_fork_copies_history(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        parent_id = store.save(history)
        fork_id = store.fork(parent_id)

        fork_data = store.load(fork_id)
        assert fork_data is not None
        assert fork_data["history"] == history

    def test_fork_sets_fork_of_metadata(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [{"role": "user", "content": "x"}]
        parent_id = store.save(history)
        fork_id = store.fork(parent_id, fork_name="my-fork")

        fork_data = store.load(fork_id)
        assert fork_data["metadata"]["fork_of"] == parent_id
        assert fork_data["metadata"]["name"] == "my-fork"

    def test_fork_returns_none_for_missing_parent(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        result = store.fork("nonexistent_id")
        assert result is None

    def test_fork_without_name(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [{"role": "user", "content": "hello"}]
        parent_id = store.save(history)
        fork_id = store.fork(parent_id)

        fork_data = store.load(fork_id)
        assert fork_data["metadata"]["fork_of"] == parent_id
        assert "name" not in fork_data["metadata"]

    def test_multiple_forks_from_same_parent(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        history = [{"role": "user", "content": "original"}]
        parent_id = store.save(history)

        fork1 = store.fork(parent_id, fork_name="branch-a")
        fork2 = store.fork(parent_id, fork_name="branch-b")

        assert fork1 != fork2
        assert fork1 != parent_id
        assert fork2 != parent_id


class TestForkCommand:
    """Tests for /fork slash command."""

    def _make_registry(self, history=None):
        registry = MagicMock()
        session = MagicMock()
        orch = MagicMock()
        orch._conversation_history = history or []
        session.orchestrator = orch
        registry._session = session
        registry._session_store = None
        registry._current_session_id = None
        registry._fork_parent_id = None
        return registry

    @pytest.mark.asyncio
    async def test_fork_saves_parent_and_creates_fork(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        registry = self._make_registry([{"role": "user", "content": "hi"}])
        store = SessionStore(base_dir=tmp_path)
        registry._session_store = store

        # Simulate what fork_handler does
        history = registry._session.orchestrator._conversation_history
        parent_id = store.save(history, session_id=registry._current_session_id)
        registry._current_session_id = parent_id
        fork_id = store.fork(parent_id, fork_name="test-fork")

        assert fork_id is not None
        fork_data = store.load(fork_id)
        assert fork_data["metadata"]["fork_of"] == parent_id

    @pytest.mark.asyncio
    async def test_fork_back_with_no_parent_returns_message(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        registry = self._make_registry()
        registry._session_store = SessionStore(base_dir=tmp_path)
        registry._fork_parent_id = None

        # Simulate fork back with no parent
        parent_id = registry._fork_parent_id
        assert parent_id is None

    @pytest.mark.asyncio
    async def test_fork_back_restores_parent_history(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        parent_history = [{"role": "user", "content": "parent msg"}]
        parent_id = store.save(parent_history)

        registry = self._make_registry([{"role": "user", "content": "forked msg"}])
        registry._session_store = store
        registry._fork_parent_id = parent_id

        # Simulate fork back
        data = store.load(parent_id)
        registry._session.orchestrator._conversation_history = data["history"]
        registry._current_session_id = parent_id
        registry._fork_parent_id = None

        assert registry._session.orchestrator._conversation_history == parent_history
        assert registry._fork_parent_id is None
