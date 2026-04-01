"""Tests for lidco.auth.keychain."""

from __future__ import annotations

import json
from pathlib import Path

from lidco.auth.keychain import KeychainEntry, KeychainStorage


def test_set_and_get():
    kc = KeychainStorage()
    kc.set("svc", "api_key", "secret123")
    assert kc.get("svc", "api_key") == "secret123"


def test_get_missing():
    kc = KeychainStorage()
    assert kc.get("nope", "nope") is None


def test_delete():
    kc = KeychainStorage()
    kc.set("svc", "k", "v")
    assert kc.delete("svc", "k") is True
    assert kc.delete("svc", "k") is False
    assert kc.get("svc", "k") is None


def test_has():
    kc = KeychainStorage()
    assert kc.has("s", "k") is False
    kc.set("s", "k", "v")
    assert kc.has("s", "k") is True


def test_list_entries_all():
    kc = KeychainStorage()
    kc.set("beta", "k1", "v1")
    kc.set("alpha", "k2", "v2")
    entries = kc.list_entries()
    assert len(entries) == 2
    assert entries[0].service == "alpha"


def test_list_entries_filtered():
    kc = KeychainStorage()
    kc.set("a", "k1", "v1")
    kc.set("b", "k2", "v2")
    assert len(kc.list_entries("a")) == 1
    assert kc.list_entries("a")[0].service == "a"


def test_save_and_load(tmp_path: Path):
    kc = KeychainStorage()
    kc.set("svc", "key", "val")
    path = tmp_path / "keychain.json"
    result = kc.save(path)
    assert result == str(path)
    assert path.exists()

    kc2 = KeychainStorage()
    count = kc2.load(path)
    assert count == 1
    assert kc2.get("svc", "key") == "val"


def test_save_no_path_raises():
    kc = KeychainStorage()
    try:
        kc.save()
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_clear():
    kc = KeychainStorage()
    kc.set("a", "k1", "v1")
    kc.set("b", "k2", "v2")
    assert kc.clear() == 2
    assert kc.list_entries() == []
