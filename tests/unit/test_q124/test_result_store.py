"""Tests for src/lidco/execution/result_store.py."""
from __future__ import annotations

import time
from unittest.mock import patch

from lidco.execution.result_store import ResultStore, StoredResult


# ------------------------------------------------------------------ #
# StoredResult                                                         #
# ------------------------------------------------------------------ #

class TestStoredResult:
    def test_fields(self):
        r = StoredResult(id="1", key="k", value="v", created_at=100.0)
        assert r.id == "1"
        assert r.key == "k"
        assert r.value == "v"
        assert r.created_at == 100.0
        assert r.ttl is None

    def test_not_expired_no_ttl(self):
        r = StoredResult(id="1", key="k", value="v", created_at=time.time())
        assert not r.is_expired

    def test_not_expired_within_ttl(self):
        r = StoredResult(id="1", key="k", value="v", created_at=time.time(), ttl=60.0)
        assert not r.is_expired

    def test_expired_past_ttl(self):
        r = StoredResult(id="1", key="k", value="v", created_at=time.time() - 100.0, ttl=10.0)
        assert r.is_expired


# ------------------------------------------------------------------ #
# ResultStore                                                          #
# ------------------------------------------------------------------ #

class TestResultStore:
    def test_put_and_get(self):
        store = ResultStore()
        store.put("k", "hello")
        assert store.get("k") == "hello"

    def test_get_missing_returns_none(self):
        store = ResultStore()
        assert store.get("missing") is None

    def test_put_returns_stored_result(self):
        store = ResultStore()
        r = store.put("k", 42)
        assert isinstance(r, StoredResult)
        assert r.key == "k"
        assert r.value == 42

    def test_overwrite_key(self):
        store = ResultStore()
        store.put("k", "first")
        store.put("k", "second")
        assert store.get("k") == "second"

    def test_delete_existing(self):
        store = ResultStore()
        store.put("k", "v")
        result = store.delete("k")
        assert result is True
        assert store.get("k") is None

    def test_delete_missing(self):
        store = ResultStore()
        result = store.delete("missing")
        assert result is False

    def test_keys_returns_all(self):
        store = ResultStore()
        store.put("a", 1)
        store.put("b", 2)
        keys = store.keys()
        assert set(keys) == {"a", "b"}

    def test_keys_empty(self):
        store = ResultStore()
        assert store.keys() == []

    def test_len(self):
        store = ResultStore()
        assert len(store) == 0
        store.put("a", 1)
        store.put("b", 2)
        assert len(store) == 2

    def test_clear_empties_store(self):
        store = ResultStore()
        store.put("a", 1)
        store.put("b", 2)
        store.clear()
        assert len(store) == 0
        assert store.keys() == []

    def test_ttl_expiry(self):
        store = ResultStore()
        with patch("lidco.execution.result_store.time") as mock_time:
            mock_time.time.return_value = 1000.0
            store.put("k", "v", ttl=10.0)
            # Still valid
            mock_time.time.return_value = 1005.0
            assert store.get("k") == "v"
            # Expired
            mock_time.time.return_value = 1015.0
            assert store.get("k") is None

    def test_clear_expired_removes_expired(self):
        store = ResultStore()
        with patch("lidco.execution.result_store.time") as mock_time:
            mock_time.time.return_value = 1000.0
            store.put("expired1", "v1", ttl=5.0)
            store.put("expired2", "v2", ttl=5.0)
            store.put("fresh", "v3", ttl=100.0)
            mock_time.time.return_value = 1010.0
            count = store.clear_expired()
        assert count == 2

    def test_clear_expired_keeps_valid(self):
        store = ResultStore()
        store.put("fresh", "v", ttl=3600.0)
        count = store.clear_expired()
        assert count == 0
        assert store.get("fresh") == "v"

    def test_clear_expired_no_ttl_kept(self):
        store = ResultStore()
        store.put("no_ttl", "v")
        count = store.clear_expired()
        assert count == 0
        assert store.get("no_ttl") == "v"

    def test_put_none_value(self):
        store = ResultStore()
        store.put("k", None)
        # None stored — but get returns None for both missing and None value
        # Key should still exist
        assert "k" in store.keys()

    def test_various_value_types(self):
        store = ResultStore()
        store.put("int", 42)
        store.put("list", [1, 2, 3])
        store.put("dict", {"a": 1})
        assert store.get("int") == 42
        assert store.get("list") == [1, 2, 3]
        assert store.get("dict") == {"a": 1}
