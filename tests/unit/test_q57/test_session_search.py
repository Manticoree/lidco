"""Tests for Task 384 — Session search via /session list --query --since."""
from __future__ import annotations

import time
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta


class TestSessionStoreSearch:
    """Tests for SessionStore.search() method."""

    def test_search_returns_all_when_no_filter(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        store.save([{"role": "user", "content": "hello world"}])
        store.save([{"role": "user", "content": "goodbye world"}])

        results = store.search()
        assert len(results) == 2

    def test_search_by_query_filters_content(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        store.save([{"role": "user", "content": "authenticate the user with JWT"}])
        store.save([{"role": "user", "content": "render the homepage"}])

        results = store.search(query="jwt")
        assert len(results) == 1
        assert "jwt" in results[0]["first_user_message"].lower() or \
               "jwt" in str(results[0]).lower()

    def test_search_by_query_case_insensitive(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        store.save([{"role": "user", "content": "AUTH flow setup"}])

        results = store.search(query="auth")
        assert len(results) == 1

    def test_search_returns_first_user_message(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        store.save([
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Fix the login bug"},
            {"role": "assistant", "content": "Sure"},
        ])

        results = store.search()
        assert len(results) == 1
        assert "Fix the login bug" in results[0]["first_user_message"]

    def test_search_by_since_days_filters_old_sessions(self, tmp_path):
        import json
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)

        # Manually create an "old" session file
        old_dt = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        old_data = {
            "session_id": "old_session",
            "saved_at": old_dt,
            "history": [{"role": "user", "content": "old message"}],
            "metadata": {},
        }
        (tmp_path / "old_session.json").write_text(
            json.dumps(old_data), encoding="utf-8"
        )

        # Recent session
        store.save([{"role": "user", "content": "recent message"}])

        results = store.search(since_days=7)
        session_ids = [r["session_id"] for r in results]
        assert "old_session" not in session_ids
        assert any("recent" in r["first_user_message"] for r in results)

    def test_search_empty_store_returns_empty_list(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path / "nosessions")
        results = store.search(query="anything")
        assert results == []

    def test_search_no_match_returns_empty_list(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        store.save([{"role": "user", "content": "completely unrelated"}])

        results = store.search(query="xyzzy_not_found")
        assert results == []

    def test_search_result_fields(self, tmp_path):
        from lidco.cli.session_store import SessionStore

        store = SessionStore(base_dir=tmp_path)
        store.save(
            [{"role": "user", "content": "check this out"}],
            metadata={"name": "test"},
        )

        results = store.search()
        assert len(results) == 1
        r = results[0]
        assert "session_id" in r
        assert "saved_at" in r
        assert "message_count" in r
        assert "metadata" in r
        assert "first_user_message" in r
        assert r["message_count"] == 1
