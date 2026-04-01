"""Tests for lidco.transcript.search."""
from __future__ import annotations

import time

from lidco.transcript.search import SearchMatch, TranscriptSearch
from lidco.transcript.store import TranscriptStore


def _populated_store() -> TranscriptStore:
    store = TranscriptStore()
    store.append("user", "Please fix the bug in auth module")
    store.append("assistant", "I found the bug in authentication logic")
    store.append("user", "Now add tests for the fix")
    store.append("tool", "All 5 tests passed", tool_name="pytest")
    return store


class TestTranscriptSearch:
    def test_regex_search_basic(self):
        store = _populated_store()
        search = TranscriptSearch(store)
        matches = search.regex_search("bug")
        assert len(matches) == 2

    def test_regex_search_with_role(self):
        store = _populated_store()
        search = TranscriptSearch(store)
        matches = search.regex_search("bug", role="user")
        assert len(matches) == 1
        assert matches[0].entry.role == "user"

    def test_regex_search_pattern(self):
        store = _populated_store()
        search = TranscriptSearch(store)
        matches = search.regex_search(r"\d+ tests")
        assert len(matches) == 1
        assert matches[0].entry.tool_name == "pytest"

    def test_fuzzy_search(self):
        store = TranscriptStore()
        store.append("user", "authentication")
        store.append("user", "something completely different and very long text")
        search = TranscriptSearch(store)
        matches = search.fuzzy_search("authenticaton", threshold=0.6)
        # Should match the first entry (close spelling)
        assert any(m.entry.content == "authentication" for m in matches)

    def test_highlight(self):
        store = TranscriptStore()
        search = TranscriptSearch(store)
        result = search.highlight("fix the bug now", "bug")
        assert result == "fix the **bug** now"

    def test_highlight_multiple(self):
        store = TranscriptStore()
        search = TranscriptSearch(store)
        result = search.highlight("bug here and bug there", "bug")
        assert result == "**bug** here and **bug** there"

    def test_filter_by_time(self):
        store = TranscriptStore()
        e1 = store.append("user", "first")
        now = time.time()
        e2 = store.append("user", "second")
        search = TranscriptSearch(store)
        # Filter with start after first entry
        filtered = search.filter_by_time(start=now - 1)
        assert len(filtered) == 2
        # Filter with end before now should include both
        filtered2 = search.filter_by_time(end=now + 10)
        assert len(filtered2) == 2

    def test_count_matches(self):
        store = _populated_store()
        search = TranscriptSearch(store)
        assert search.count_matches("bug") == 2
        assert search.count_matches("nonexistent") == 0
