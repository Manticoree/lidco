"""Tests for SessionManager — Task 306."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from lidco.server.session_manager import (
    SessionInfo,
    SessionLimitError,
    SessionManager,
    SessionNotFoundError,
)


# ---------------------------------------------------------------------------
# create() / inject()
# ---------------------------------------------------------------------------

class TestSessionManagerCreate:
    def test_create_returns_string_id(self):
        mgr = SessionManager()
        sid = mgr.create()
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_create_ids_are_unique(self):
        mgr = SessionManager()
        ids = {mgr.create() for _ in range(10)}
        assert len(ids) == 10

    def test_create_with_factory(self):
        mock_session = MagicMock()
        mgr = SessionManager(session_factory=lambda: mock_session)
        sid = mgr.create()
        session = mgr.get(sid)
        assert session is mock_session

    def test_create_with_tags(self):
        mgr = SessionManager()
        sid = mgr.create(tags=["ci", "test"])
        info = mgr.info(sid)
        assert "ci" in info.tags
        assert "test" in info.tags

    def test_create_raises_on_limit(self):
        mgr = SessionManager(max_sessions=2)
        mgr.create()
        mgr.create()
        with pytest.raises(SessionLimitError):
            mgr.create()

    def test_inject_stores_session(self):
        mgr = SessionManager()
        mock_session = MagicMock()
        sid = mgr.inject(mock_session)
        assert mgr.get(sid) is mock_session

    def test_inject_custom_id(self):
        mgr = SessionManager()
        mock_session = MagicMock()
        sid = mgr.inject(mock_session, session_id="my-session")
        assert sid == "my-session"
        assert mgr.get("my-session") is mock_session

    def test_inject_raises_on_limit(self):
        mgr = SessionManager(max_sessions=1)
        mgr.inject(MagicMock())
        with pytest.raises(SessionLimitError):
            mgr.inject(MagicMock())


# ---------------------------------------------------------------------------
# get() / info()
# ---------------------------------------------------------------------------

class TestSessionManagerGet:
    def test_get_existing_session(self):
        mgr = SessionManager()
        mock_session = MagicMock()
        sid = mgr.inject(mock_session)
        assert mgr.get(sid) is mock_session

    def test_get_missing_raises(self):
        mgr = SessionManager()
        with pytest.raises(SessionNotFoundError):
            mgr.get("nonexistent-id")

    def test_get_updates_last_active(self):
        mgr = SessionManager()
        sid = mgr.inject(MagicMock())
        before = mgr.info(sid).last_active
        time.sleep(0.01)
        mgr.get(sid)
        after = mgr.info(sid).last_active
        assert after >= before

    def test_info_existing(self):
        mgr = SessionManager()
        sid = mgr.inject(MagicMock())
        info = mgr.info(sid)
        assert info.session_id == sid
        assert isinstance(info.created_at, float)

    def test_info_missing_raises(self):
        mgr = SessionManager()
        with pytest.raises(SessionNotFoundError):
            mgr.info("ghost")


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------

class TestSessionManagerClose:
    def test_close_existing_returns_true(self):
        mgr = SessionManager()
        sid = mgr.inject(MagicMock())
        assert mgr.close(sid) is True

    def test_close_removes_session(self):
        mgr = SessionManager()
        sid = mgr.inject(MagicMock())
        mgr.close(sid)
        with pytest.raises(SessionNotFoundError):
            mgr.get(sid)

    def test_close_missing_returns_false(self):
        mgr = SessionManager()
        assert mgr.close("ghost") is False

    def test_close_frees_slot_for_new_session(self):
        mgr = SessionManager(max_sessions=1)
        sid = mgr.inject(MagicMock())
        mgr.close(sid)
        # Should not raise now
        mgr.inject(MagicMock())

    def test_close_all(self):
        mgr = SessionManager()
        for _ in range(3):
            mgr.inject(MagicMock())
        closed = mgr.close_all()
        assert closed == 3
        assert mgr.count() == 0


# ---------------------------------------------------------------------------
# list_sessions() / count()
# ---------------------------------------------------------------------------

class TestSessionManagerList:
    def test_list_empty(self):
        mgr = SessionManager()
        assert mgr.list_sessions() == []

    def test_list_returns_all_sessions(self):
        mgr = SessionManager()
        s1 = mgr.inject(MagicMock())
        s2 = mgr.inject(MagicMock())
        ids = {info.session_id for info in mgr.list_sessions()}
        assert s1 in ids
        assert s2 in ids

    def test_list_sorted_by_created_at(self):
        mgr = SessionManager()
        ids = [mgr.inject(MagicMock()) for _ in range(3)]
        listed = [info.session_id for info in mgr.list_sessions()]
        # Order should be creation order
        assert listed == ids

    def test_count(self):
        mgr = SessionManager()
        assert mgr.count() == 0
        mgr.inject(MagicMock())
        mgr.inject(MagicMock())
        assert mgr.count() == 2


# ---------------------------------------------------------------------------
# record_turn()
# ---------------------------------------------------------------------------

class TestSessionManagerRecordTurn:
    def test_record_turn_increments_count(self):
        mgr = SessionManager()
        sid = mgr.inject(MagicMock())
        assert mgr.info(sid).turn_count == 0
        mgr.record_turn(sid)
        mgr.record_turn(sid)
        assert mgr.info(sid).turn_count == 2

    def test_record_turn_missing_session_noop(self):
        mgr = SessionManager()
        mgr.record_turn("ghost")  # should not raise


# ---------------------------------------------------------------------------
# SessionInfo
# ---------------------------------------------------------------------------

class TestSessionInfo:
    def test_idle_seconds(self):
        now = time.time()
        info = SessionInfo(
            session_id="x",
            created_at=now - 10,
            last_active=now - 5,
        )
        assert info.idle_seconds >= 5
