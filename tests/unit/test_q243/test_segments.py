"""Tests for Q243 ContextSegments."""
from __future__ import annotations

import pytest

from lidco.context.segments import ContextSegments, Segment


class TestContextSegmentsCreate:
    def test_create_segment(self):
        cs = ContextSegments()
        cs.create_segment("code", 1000)
        seg = cs.get_segment("code")
        assert seg is not None
        assert seg.name == "code"
        assert seg.budget == 1000

    def test_create_duplicate_raises(self):
        cs = ContextSegments()
        cs.create_segment("code", 1000)
        with pytest.raises(ValueError, match="already exists"):
            cs.create_segment("code", 2000)

    def test_create_multiple(self):
        cs = ContextSegments()
        cs.create_segment("a", 100)
        cs.create_segment("b", 200)
        assert len(cs.list_segments()) == 2


class TestContextSegmentsWithDefaults:
    def test_with_defaults_creates_four_segments(self):
        cs = ContextSegments.with_defaults()
        names = {s.name for s in cs.list_segments()}
        assert names == {"system", "tools", "history", "active"}

    def test_with_defaults_budgets(self):
        cs = ContextSegments.with_defaults()
        assert cs.get_segment("system").budget == 2000
        assert cs.get_segment("tools").budget == 4000
        assert cs.get_segment("history").budget == 8000
        assert cs.get_segment("active").budget == 16000


class TestContextSegmentsAddEntry:
    def test_add_to_segment(self):
        cs = ContextSegments()
        cs.create_segment("code", 1000)
        assert cs.add_to_segment("code", "some content") is True
        seg = cs.get_segment("code")
        assert len(seg.entries) == 1

    def test_add_to_missing_segment(self):
        cs = ContextSegments()
        assert cs.add_to_segment("nope", "content") is False

    def test_add_over_budget(self):
        cs = ContextSegments()
        cs.create_segment("tiny", 1)  # 1 token budget
        # 100 chars = 25 tokens, over budget
        assert cs.add_to_segment("tiny", "x" * 100) is False

    def test_add_updates_used(self):
        cs = ContextSegments()
        cs.create_segment("code", 1000)
        cs.add_to_segment("code", "hello world")  # ~2-3 tokens
        seg = cs.get_segment("code")
        assert seg.used > 0

    def test_add_multiple_entries(self):
        cs = ContextSegments()
        cs.create_segment("code", 10000)
        cs.add_to_segment("code", "entry1")
        cs.add_to_segment("code", "entry2")
        seg = cs.get_segment("code")
        assert len(seg.entries) == 2


class TestContextSegmentsRemoveEntry:
    def test_remove_from_segment(self):
        cs = ContextSegments()
        cs.create_segment("code", 1000)
        cs.add_to_segment("code", "hello")
        assert cs.remove_from_segment("code", "hello") is True
        seg = cs.get_segment("code")
        assert len(seg.entries) == 0

    def test_remove_missing_entry(self):
        cs = ContextSegments()
        cs.create_segment("code", 1000)
        assert cs.remove_from_segment("code", "nope") is False

    def test_remove_from_missing_segment(self):
        cs = ContextSegments()
        assert cs.remove_from_segment("nope", "entry") is False

    def test_remove_decreases_used(self):
        cs = ContextSegments()
        cs.create_segment("code", 1000)
        cs.add_to_segment("code", "hello world")
        used_before = cs.get_segment("code").used
        cs.remove_from_segment("code", "hello world")
        assert cs.get_segment("code").used < used_before


class TestContextSegmentsResize:
    def test_resize(self):
        cs = ContextSegments()
        cs.create_segment("code", 1000)
        assert cs.resize("code", 2000) is True
        assert cs.get_segment("code").budget == 2000

    def test_resize_missing(self):
        cs = ContextSegments()
        assert cs.resize("nope", 100) is False

    def test_resize_preserves_entries(self):
        cs = ContextSegments()
        cs.create_segment("code", 1000)
        cs.add_to_segment("code", "entry1")
        cs.resize("code", 2000)
        seg = cs.get_segment("code")
        assert len(seg.entries) == 1


class TestContextSegmentsStats:
    def test_stats_empty(self):
        cs = ContextSegments()
        s = cs.stats()
        assert s["segment_count"] == 0
        assert s["total_budget"] == 0

    def test_stats_with_segments(self):
        cs = ContextSegments()
        cs.create_segment("a", 100)
        cs.create_segment("b", 200)
        s = cs.stats()
        assert s["segment_count"] == 2
        assert s["total_budget"] == 300

    def test_stats_tracks_used(self):
        cs = ContextSegments()
        cs.create_segment("code", 10000)
        cs.add_to_segment("code", "some content here")
        s = cs.stats()
        assert s["total_used"] > 0
