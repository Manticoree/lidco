"""Tests for Q41 — SessionStore (Task 285)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lidco.cli.session_store import SessionStore


@pytest.fixture()
def store(tmp_path) -> SessionStore:
    return SessionStore(base_dir=tmp_path / "sessions")


class TestSessionStoreSave:
    def test_save_returns_session_id(self, store):
        sid = store.save([{"role": "user", "content": "hi"}])
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_save_with_explicit_id(self, store):
        sid = store.save([], session_id="my-session")
        assert sid == "my-session"

    def test_save_creates_file(self, store):
        sid = store.save([{"role": "user", "content": "hi"}])
        p = store._path(sid)
        assert p.exists()

    def test_save_file_is_valid_json(self, store):
        sid = store.save([{"role": "user", "content": "test"}])
        data = json.loads(store._path(sid).read_text())
        assert data["session_id"] == sid
        assert "history" in data
        assert "saved_at" in data

    def test_save_metadata(self, store):
        sid = store.save([], metadata={"model": "gpt-4"})
        data = json.loads(store._path(sid).read_text())
        assert data["metadata"]["model"] == "gpt-4"


class TestSessionStoreLoad:
    def test_load_existing(self, store):
        history = [{"role": "user", "content": "hello"}]
        sid = store.save(history)
        data = store.load(sid)
        assert data is not None
        assert data["history"] == history

    def test_load_nonexistent_returns_none(self, store):
        assert store.load("no-such-session") is None

    def test_load_corrupt_file_returns_none(self, store, tmp_path):
        store._ensure_dir()
        bad = store._path("bad")
        bad.write_text("not json")
        assert store.load("bad") is None


class TestSessionStoreList:
    def test_list_empty(self, store):
        assert store.list_sessions() == []

    def test_list_returns_all(self, store):
        store.save([], session_id="a")
        store.save([], session_id="b")
        sessions = store.list_sessions()
        ids = {s["session_id"] for s in sessions}
        assert "a" in ids
        assert "b" in ids

    def test_list_includes_message_count(self, store):
        history = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]
        sid = store.save(history)
        sessions = store.list_sessions()
        entry = next(s for s in sessions if s["session_id"] == sid)
        assert entry["message_count"] == 2

    def test_list_sorted_by_mtime_newest_first(self, store):
        import time
        store.save([], session_id="first")
        time.sleep(0.01)
        store.save([], session_id="second")
        sessions = store.list_sessions()
        assert sessions[0]["session_id"] == "second"


class TestSessionStoreDelete:
    def test_delete_existing(self, store):
        sid = store.save([])
        assert store.delete(sid) is True
        assert not store._path(sid).exists()

    def test_delete_nonexistent_returns_false(self, store):
        assert store.delete("ghost") is False

    def test_deleted_not_in_list(self, store):
        sid = store.save([])
        store.delete(sid)
        ids = {s["session_id"] for s in store.list_sessions()}
        assert sid not in ids
