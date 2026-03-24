import time
import pytest
from pathlib import Path
from lidco.memory.session_history import (
    SessionHistoryStore,
    SessionRecord,
    HistorySearchResult,
)


def make_record(sid="s1", topic="Fix auth bug", summary="Fixed JWT issue", tags=None):
    return SessionRecord(
        session_id=sid,
        topic=topic,
        started_at=time.time(),
        ended_at=time.time() + 60,
        turn_count=5,
        summary=summary,
        tags=tags or ["auth", "jwt"],
    )


def test_save_and_list_returns_records(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    store.save(make_record("s1"))
    records = store.list()
    assert len(records) == 1
    assert records[0].session_id == "s1"


def test_list_respects_limit_and_offset(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    for i in range(5):
        store.save(make_record(f"s{i}", topic=f"Topic {i}"))
    assert len(store.list(limit=2)) == 2
    assert len(store.list(limit=2, offset=3)) == 2


def test_search_matches_topic(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    store.save(make_record("s1", topic="Fix auth bug"))
    store.save(make_record("s2", topic="Refactor DB", summary="Cleaned up queries", tags=["database"]))
    result = store.search("auth")
    assert result.total == 1
    assert result.records[0].session_id == "s1"


def test_search_matches_summary(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    store.save(make_record("s1", summary="JWT token expired"))
    result = store.search("JWT")
    assert result.total == 1


def test_search_no_results_returns_empty(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    result = store.search("nonexistent_xyz_query")
    assert result.total == 0
    assert result.records == []


def test_get_by_id(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    store.save(make_record("abc123"))
    record = store.get("abc123")
    assert record is not None
    assert record.session_id == "abc123"


def test_get_unknown_id_returns_none(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    assert store.get("unknown") is None


def test_delete_removes_record(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    store.save(make_record("s1"))
    assert store.delete("s1") is True
    assert store.get("s1") is None


def test_resume_context_format(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    store.save(make_record("s1", topic="Refactor auth"))
    ctx = store.resume_context("s1")
    assert "Resumed Session" in ctx
    assert "Refactor auth" in ctx


def test_auto_topic_extraction(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    msgs = [{"role": "user", "content": "Fix the JWT token validation in the auth module"}]
    topic = store.auto_topic(msgs)
    assert "Fix" in topic or "JWT" in topic
    assert len(topic) > 0


def test_auto_topic_empty_messages(tmp_path):
    store = SessionHistoryStore(tmp_path / "h.db")
    topic = store.auto_topic([])
    assert topic == "Untitled Session"
