"""Tests for T632 KVStore."""
import time
from unittest.mock import patch

import pytest

from lidco.storage.kv_store import KVStore


class TestKVStore:
    def _make(self):
        return KVStore(path=None)

    def test_set_and_get(self):
        store = self._make()
        store.set("key", "value")
        assert store.get("key") == "value"

    def test_get_default_none(self):
        store = self._make()
        assert store.get("missing") is None

    def test_get_default_custom(self):
        store = self._make()
        assert store.get("missing", 42) == 42

    def test_delete_existing(self):
        store = self._make()
        store.set("k", "v")
        assert store.delete("k") is True
        assert store.get("k") is None

    def test_delete_nonexistent(self):
        store = self._make()
        assert store.delete("nope") is False

    def test_list_all_keys(self):
        store = self._make()
        store.set("a", 1)
        store.set("b", 2)
        store.set("c", 3)
        assert sorted(store.list()) == ["a", "b", "c"]

    def test_list_with_prefix(self):
        store = self._make()
        store.set("a:1", 1)
        store.set("a:2", 2)
        store.set("b:1", 3)
        keys = store.list("a:")
        assert sorted(keys) == ["a:1", "a:2"]

    def test_ttl_expiry(self):
        store = self._make()
        store.set("temp", "val", ttl=0.01)
        time.sleep(0.05)
        assert store.get("temp") is None

    def test_no_ttl_does_not_expire(self):
        store = self._make()
        store.set("perm", "forever")
        time.sleep(0.02)
        assert store.get("perm") == "forever"

    def test_flush_expired(self):
        store = self._make()
        store.set("x", 1, ttl=0.01)
        store.set("y", 2, ttl=0.01)
        store.set("z", 3)
        time.sleep(0.05)
        count = store.flush_expired()
        assert count == 2
        assert store.count() == 1

    def test_namespace_set_get(self):
        store = self._make()
        ns = store.ns("cache")
        ns.set("item", 99)
        assert store.get("cache:item") == 99
        assert ns.get("item") == 99

    def test_namespace_list(self):
        store = self._make()
        ns = store.ns("pfx")
        ns.set("a", 1)
        ns.set("b", 2)
        store.set("other", 3)
        keys = ns.list()
        assert sorted(keys) == ["a", "b"]

    def test_clear(self):
        store = self._make()
        store.set("a", 1)
        store.set("b", 2)
        count = store.clear()
        assert count == 2
        assert store.count() == 0

    def test_exists(self):
        store = self._make()
        store.set("k", "v")
        assert store.exists("k") is True
        assert store.exists("nope") is False

    def test_persistence_save_load(self, tmp_path):
        path = tmp_path / "kv.json"
        s1 = KVStore(path=str(path))
        s1.set("hello", "world")
        s1.save()
        s2 = KVStore(path=str(path))
        assert s2.get("hello") == "world"
