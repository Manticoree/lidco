"""Tests for ContextPager — Task 307."""

from __future__ import annotations

import pytest

from lidco.context.pager import ContextChunk, ContextPager, PageResult, _token_estimate


# ---------------------------------------------------------------------------
# _token_estimate
# ---------------------------------------------------------------------------

class TestTokenEstimate:
    def test_empty_string(self):
        assert _token_estimate("") >= 1

    def test_rough_estimate(self):
        text = "x" * 400
        assert _token_estimate(text) == 100

    def test_short_text(self):
        assert _token_estimate("hi") >= 1


# ---------------------------------------------------------------------------
# ContextChunk
# ---------------------------------------------------------------------------

class TestContextChunk:
    def test_token_count(self):
        chunk = ContextChunk(content="a" * 400)
        assert chunk.token_count == 100

    def test_defaults(self):
        chunk = ContextChunk(content="hello")
        assert chunk.priority == 0.5
        assert chunk.chunk_type == "file"
        assert chunk.source == ""


# ---------------------------------------------------------------------------
# ContextPager.add / clear / chunk_count
# ---------------------------------------------------------------------------

class TestContextPagerAdd:
    def test_add_increments_count(self):
        pager = ContextPager()
        pager.add(ContextChunk(content="x"))
        assert pager.chunk_count == 1

    def test_add_many(self):
        pager = ContextPager()
        chunks = [ContextChunk(content=f"chunk{i}") for i in range(5)]
        pager.add_many(chunks)
        assert pager.chunk_count == 5

    def test_clear(self):
        pager = ContextPager()
        pager.add(ContextChunk(content="x"))
        pager.clear()
        assert pager.chunk_count == 0


# ---------------------------------------------------------------------------
# ContextPager.page()
# ---------------------------------------------------------------------------

class TestContextPagerPage:
    def test_includes_chunks_within_budget(self):
        pager = ContextPager(token_budget=1000)
        pager.add(ContextChunk(content="a" * 100, priority=0.9))  # ~25 tokens
        result = pager.page()
        assert len(result.chunks) == 1

    def test_excludes_chunks_over_budget(self):
        pager = ContextPager(token_budget=10)
        # Each chunk is 100 tokens
        pager.add(ContextChunk(content="a" * 400, priority=0.9))
        pager.add(ContextChunk(content="b" * 400, priority=0.8))
        result = pager.page()
        # Only one (or zero) should fit
        assert result.dropped_count >= 1

    def test_higher_priority_included_first(self):
        pager = ContextPager(token_budget=50)
        # Low priority, large chunk
        pager.add(ContextChunk(content="a" * 160, priority=0.1, source="low"))
        # High priority, small chunk
        pager.add(ContextChunk(content="b" * 40, priority=0.9, source="high"))
        result = pager.page()
        sources = [c.source for c in result.chunks]
        assert "high" in sources

    def test_dropped_sources_reported(self):
        pager = ContextPager(token_budget=10)
        pager.add(ContextChunk(content="a" * 400, priority=0.5, source="dropped.py"))
        result = pager.page()
        assert "dropped.py" in result.dropped_sources

    def test_empty_pager(self):
        pager = ContextPager()
        result = pager.page()
        assert result.chunks == []
        assert result.total_tokens == 0
        assert result.dropped_count == 0

    def test_result_text_contains_source_header(self):
        pager = ContextPager(token_budget=1000)
        pager.add(ContextChunk(content="hello", source="src/main.py"))
        result = pager.page()
        assert "src/main.py" in result.text
        assert "hello" in result.text

    def test_result_text_no_source(self):
        pager = ContextPager(token_budget=1000)
        pager.add(ContextChunk(content="plain content"))
        result = pager.page()
        assert "plain content" in result.text


# ---------------------------------------------------------------------------
# PageResult.utilization
# ---------------------------------------------------------------------------

class TestPageResultUtilization:
    def test_full_budget_used(self):
        result = PageResult(
            chunks=[],
            total_tokens=100,
            budget=100,
            dropped_count=0,
            dropped_sources=[],
        )
        assert result.utilization == 1.0

    def test_zero_tokens(self):
        result = PageResult(
            chunks=[], total_tokens=0, budget=100,
            dropped_count=0, dropped_sources=[]
        )
        assert result.utilization == 0.0

    def test_zero_budget(self):
        result = PageResult(
            chunks=[], total_tokens=0, budget=0,
            dropped_count=0, dropped_sources=[]
        )
        assert result.utilization == 0.0


# ---------------------------------------------------------------------------
# Type weights
# ---------------------------------------------------------------------------

class TestTypeWeights:
    def test_system_chunk_has_high_weight(self):
        """System chunks should be preferred over file chunks at same priority."""
        pager = ContextPager(token_budget=50)
        # Make them the same size so only weight matters
        pager.add(ContextChunk(content="a" * 40, priority=0.5, chunk_type="file", source="file"))
        pager.add(ContextChunk(content="b" * 40, priority=0.5, chunk_type="system", source="system"))
        result = pager.page()
        # system should be included, file may be dropped
        sources = [c.source for c in result.chunks]
        assert "system" in sources


# ---------------------------------------------------------------------------
# Custom relevance function
# ---------------------------------------------------------------------------

class TestRelevanceFunction:
    def test_relevance_boosts_matching_chunk(self):
        def relevance(chunk, query):
            return 1.0 if query.lower() in chunk.content.lower() else 0.0

        pager = ContextPager(token_budget=50, relevance_fn=relevance)
        pager.add(ContextChunk(content="auth token handling", priority=0.3, source="auth"))
        pager.add(ContextChunk(content="unrelated content xyz", priority=0.8, source="other"))
        result = pager.page("auth")
        sources = [c.source for c in result.chunks]
        assert "auth" in sources
