"""Tests for Q243 ContextDefragmenter."""
from __future__ import annotations

import pytest

from lidco.context.defragmenter import ContextDefragmenter, DefragResult
from lidco.context.segments import ContextSegments, Segment


class TestDefragResultDataclass:
    def test_creation(self):
        r = DefragResult(merged_count=2, reclaimed_tokens=50)
        assert r.merged_count == 2
        assert r.reclaimed_tokens == 50

    def test_frozen(self):
        r = DefragResult(merged_count=0, reclaimed_tokens=0)
        with pytest.raises(AttributeError):
            r.merged_count = 5  # type: ignore[misc]


class TestContextDefragmenterCompact:
    def test_compact_no_waste(self):
        cs = ContextSegments()
        cs.create_segment("code", 10000)
        cs.add_to_segment("code", "hello world test")
        defrag = ContextDefragmenter(cs)
        reclaimed = defrag.compact("code")
        assert reclaimed == 0

    def test_compact_with_inflated_used(self):
        cs = ContextSegments()
        # Manually create a segment with inflated `used`
        cs._segments["bloated"] = Segment(name="bloated", budget=1000, used=500, entries=["hi"])
        defrag = ContextDefragmenter(cs)
        reclaimed = defrag.compact("bloated")
        assert reclaimed > 0
        assert cs.get_segment("bloated").used < 500

    def test_compact_missing_segment(self):
        cs = ContextSegments()
        defrag = ContextDefragmenter(cs)
        assert defrag.compact("nope") == 0

    def test_compact_empty_segment(self):
        cs = ContextSegments()
        cs.create_segment("empty", 1000)
        defrag = ContextDefragmenter(cs)
        assert defrag.compact("empty") == 0


class TestContextDefragmenterMergeSmall:
    def test_merge_small_below_threshold(self):
        cs = ContextSegments()
        cs._segments["a"] = Segment(name="a", budget=100, used=10, entries=["x"])
        cs._segments["b"] = Segment(name="b", budget=100, used=10, entries=["y"])
        defrag = ContextDefragmenter(cs)
        merged = defrag.merge_small(threshold=100)
        assert merged == 2
        assert cs.get_segment("_merged") is not None
        assert "x" in cs.get_segment("_merged").entries
        assert "y" in cs.get_segment("_merged").entries

    def test_merge_small_one_segment_no_merge(self):
        cs = ContextSegments()
        cs._segments["a"] = Segment(name="a", budget=100, used=10, entries=["x"])
        defrag = ContextDefragmenter(cs)
        merged = defrag.merge_small(threshold=100)
        assert merged == 0

    def test_merge_small_above_threshold_untouched(self):
        cs = ContextSegments()
        cs._segments["big"] = Segment(name="big", budget=1000, used=500, entries=["x"])
        cs._segments["small"] = Segment(name="small", budget=100, used=10, entries=["y"])
        defrag = ContextDefragmenter(cs)
        merged = defrag.merge_small(threshold=100)
        assert merged == 0  # only 1 below threshold, need 2
        assert cs.get_segment("big") is not None

    def test_merge_small_preserves_large(self):
        cs = ContextSegments()
        cs._segments["big"] = Segment(name="big", budget=1000, used=500, entries=["x"])
        cs._segments["a"] = Segment(name="a", budget=100, used=10, entries=["y"])
        cs._segments["b"] = Segment(name="b", budget=100, used=20, entries=["z"])
        defrag = ContextDefragmenter(cs)
        defrag.merge_small(threshold=100)
        assert cs.get_segment("big") is not None
        assert cs.get_segment("big").used == 500

    def test_merge_small_accumulates_budget(self):
        cs = ContextSegments()
        cs._segments["a"] = Segment(name="a", budget=100, used=10, entries=[])
        cs._segments["b"] = Segment(name="b", budget=200, used=20, entries=[])
        defrag = ContextDefragmenter(cs)
        defrag.merge_small(threshold=100)
        merged = cs.get_segment("_merged")
        assert merged.budget == 300
        assert merged.used == 30


class TestContextDefragmenterDefragment:
    def test_defragment_returns_result(self):
        cs = ContextSegments()
        cs._segments["a"] = Segment(name="a", budget=100, used=10, entries=["x"])
        cs._segments["b"] = Segment(name="b", budget=100, used=10, entries=["y"])
        defrag = ContextDefragmenter(cs)
        result = defrag.defragment()
        assert isinstance(result, DefragResult)
        assert result.merged_count >= 0

    def test_defragment_empty(self):
        cs = ContextSegments()
        defrag = ContextDefragmenter(cs)
        result = defrag.defragment()
        assert result.merged_count == 0
        assert result.reclaimed_tokens == 0

    def test_defragment_increments_count(self):
        cs = ContextSegments()
        defrag = ContextDefragmenter(cs)
        defrag.defragment()
        defrag.defragment()
        assert defrag.stats()["defrag_count"] == 2


class TestContextDefragmenterStats:
    def test_stats_initial(self):
        cs = ContextSegments()
        defrag = ContextDefragmenter(cs)
        s = defrag.stats()
        assert s["defrag_count"] == 0
        assert s["total_reclaimed"] == 0

    def test_stats_after_compact(self):
        cs = ContextSegments()
        cs._segments["bloated"] = Segment(name="bloated", budget=1000, used=500, entries=["hi"])
        defrag = ContextDefragmenter(cs)
        defrag.compact("bloated")
        s = defrag.stats()
        assert s["total_reclaimed"] > 0

    def test_stats_segment_count(self):
        cs = ContextSegments()
        cs.create_segment("a", 100)
        cs.create_segment("b", 200)
        defrag = ContextDefragmenter(cs)
        assert defrag.stats()["segment_count"] == 2
