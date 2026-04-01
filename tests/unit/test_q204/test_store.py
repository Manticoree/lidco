"""Tests for lidco.transcript.store."""
from __future__ import annotations

import json
import time

from lidco.transcript.store import TranscriptEntry, TranscriptError, TranscriptStore


class TestTranscriptEntry:
    def test_frozen(self):
        entry = TranscriptEntry(
            id="abc", role="user", content="hello", timestamp=1.0
        )
        assert entry.id == "abc"
        assert entry.tool_name == ""
        assert entry.metadata == {}
        try:
            entry.role = "system"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestTranscriptStore:
    def test_append_and_count(self):
        store = TranscriptStore()
        assert store.count() == 0
        e = store.append("user", "hello world")
        assert store.count() == 1
        assert e.role == "user"
        assert e.content == "hello world"
        assert len(e.id) == 8

    def test_get(self):
        store = TranscriptStore()
        e = store.append("assistant", "response")
        found = store.get(e.id)
        assert found is not None
        assert found.content == "response"
        assert store.get("nonexistent") is None

    def test_search_substring(self):
        store = TranscriptStore()
        store.append("user", "find the needle here")
        store.append("assistant", "no match")
        store.append("user", "another NEEDLE case")
        results = store.search("needle")
        assert len(results) == 2

    def test_search_with_role_filter(self):
        store = TranscriptStore()
        store.append("user", "alpha beta")
        store.append("assistant", "alpha gamma")
        results = store.search("alpha", role="user")
        assert len(results) == 1
        assert results[0].role == "user"

    def test_list_entries(self):
        store = TranscriptStore()
        store.append("user", "a")
        store.append("assistant", "b")
        store.append("user", "c")
        assert len(store.list_entries()) == 3
        assert len(store.list_entries(role="user")) == 2
        assert len(store.list_entries(limit=1)) == 1

    def test_clear(self):
        store = TranscriptStore()
        store.append("user", "x")
        store.append("user", "y")
        removed = store.clear()
        assert removed == 2
        assert store.count() == 0

    def test_save_and_load_jsonl(self, tmp_path):
        store = TranscriptStore()
        store.append("user", "line one")
        store.append("assistant", "line two", tool_name="tool1")
        path = tmp_path / "transcript.jsonl"
        result_path = store.save(path)
        assert result_path == str(path)
        assert path.exists()

        store2 = TranscriptStore()
        loaded = store2.load(path)
        assert loaded == 2
        assert store2.count() == 2
        entries = store2.list_entries()
        assert entries[0].content == "line one"
        assert entries[1].tool_name == "tool1"

    def test_save_no_path_raises(self):
        store = TranscriptStore()
        try:
            store.save()
            assert False, "Should raise"
        except TranscriptError:
            pass

    def test_load_missing_file_raises(self):
        store = TranscriptStore()
        try:
            store.load("/nonexistent/path.jsonl")
            assert False, "Should raise"
        except TranscriptError:
            pass

    def test_append_with_metadata(self):
        store = TranscriptStore()
        e = store.append("tool", "result", tool_name="bash", metadata={"exit": 0})
        assert e.tool_name == "bash"
        assert e.metadata == {"exit": 0}
