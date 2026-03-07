"""Tests for WebSearchTool caching and richer output (Q32, Task 149)."""

from __future__ import annotations

import sys
import time
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from lidco.tools.web_search import WebSearchTool


def _tool() -> WebSearchTool:
    return WebSearchTool()


def _mock_ddgs(results: list[dict], *, raise_exc: Exception | None = None) -> MagicMock:
    """Return a mock DDGS context-manager class."""
    mock_cls = MagicMock()
    mock_inst = MagicMock()
    if raise_exc is not None:
        mock_inst.text.side_effect = raise_exc
    else:
        mock_inst.text.return_value = results
    mock_cls.return_value.__enter__.return_value = mock_inst
    mock_cls.return_value.__exit__.return_value = None
    return mock_cls


def _ddgs_module(ddgs_cls: MagicMock) -> ModuleType:
    mod = ModuleType("duckduckgo_search")
    mod.DDGS = ddgs_cls  # type: ignore[attr-defined]
    return mod


class TestWebSearchCache:
    """Cache hit/miss, TTL expiry."""

    def test_cache_starts_empty(self):
        t = _tool()
        assert len(t._cache) == 0

    @pytest.mark.asyncio
    async def test_cache_hit_returns_same_result(self):
        t = _tool()
        fake = [{"title": "Python docs", "href": "https://docs.python.org/asyncio", "body": "Async I/O"}]
        ddgs_cls = _mock_ddgs(fake)
        mod = _ddgs_module(ddgs_cls)
        with __import__("unittest.mock", fromlist=["patch"]).patch.dict(sys.modules, {"duckduckgo_search": mod}):
            r1 = await t._run(query="python asyncio", max_results=3)
            r2 = await t._run(query="python asyncio", max_results=3)

        assert ddgs_cls.return_value.__enter__.return_value.text.call_count == 1
        assert r1.output == r2.output
        assert r1.success and r2.success

    @pytest.mark.asyncio
    async def test_different_queries_not_cached(self):
        t = _tool()
        fake = [{"title": "X", "href": "https://x.com", "body": "desc"}]
        ddgs_cls = _mock_ddgs(fake)
        mod = _ddgs_module(ddgs_cls)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            await t._run(query="python", max_results=3)
            await t._run(query="asyncio", max_results=3)

        assert ddgs_cls.return_value.__enter__.return_value.text.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_ttl_expiry(self):
        t = _tool()
        fake = [{"title": "Y", "href": "https://y.com", "body": "snippet"}]
        cache_key = "ttl test"

        # Insert a stale cache entry (timestamp = 0 = expired)
        t._cache[cache_key] = (0.0, "stale result")

        ddgs_cls = _mock_ddgs(fake)
        mod = _ddgs_module(ddgs_cls)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await t._run(query=cache_key, max_results=3)

        assert ddgs_cls.return_value.__enter__.return_value.text.call_count == 1
        assert result.output != "stale result"

    @pytest.mark.asyncio
    async def test_cache_fresh_not_expired(self):
        t = _tool()
        cache_key = "fresh query"
        fresh_output = "fresh cached result"
        t._cache[cache_key] = (time.monotonic(), fresh_output)

        ddgs_cls = _mock_ddgs([])
        mod = _ddgs_module(ddgs_cls)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await t._run(query=cache_key, max_results=3)

        assert ddgs_cls.return_value.__enter__.return_value.text.call_count == 0
        assert result.output == fresh_output

    @pytest.mark.asyncio
    async def test_failed_search_not_cached(self):
        t = _tool()
        ddgs_cls = _mock_ddgs([], raise_exc=RuntimeError("network error"))
        mod = _ddgs_module(ddgs_cls)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await t._run(query="fail query", max_results=3)

        assert not result.success
        assert "fail query" not in t._cache

    @pytest.mark.asyncio
    async def test_cache_stores_result_on_success(self):
        t = _tool()
        fake = [{"title": "Z", "href": "https://z.com", "body": "body"}]
        ddgs_cls = _mock_ddgs(fake)
        mod = _ddgs_module(ddgs_cls)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            await t._run(query="cache store test", max_results=3)

        assert "cache store test" in t._cache
        ts, val = t._cache["cache store test"]
        assert ts > 0
        assert val


class TestWebSearchRicherOutput:
    """Richer output: Summary line, --- separators."""

    @pytest.mark.asyncio
    async def test_output_contains_summary_line(self):
        t = _tool()
        fake = [
            {"title": "A", "href": "https://a.com", "body": "body A"},
            {"title": "B", "href": "https://b.com", "body": "body B"},
        ]
        ddgs_cls = _mock_ddgs(fake)
        mod = _ddgs_module(ddgs_cls)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await t._run(query="test output", max_results=2)

        assert "## Summary" in result.output
        assert "2 result" in result.output

    @pytest.mark.asyncio
    async def test_output_contains_separator_between_results(self):
        t = _tool()
        fake = [
            {"title": "A", "href": "https://a.com", "body": "body A"},
            {"title": "B", "href": "https://b.com", "body": "body B"},
        ]
        ddgs_cls = _mock_ddgs(fake)
        mod = _ddgs_module(ddgs_cls)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await t._run(query="sep test", max_results=2)

        assert "---" in result.output

    @pytest.mark.asyncio
    async def test_single_result_no_trailing_separator(self):
        t = _tool()
        fake = [{"title": "A", "href": "https://a.com", "body": "body A"}]
        ddgs_cls = _mock_ddgs(fake)
        mod = _ddgs_module(ddgs_cls)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await t._run(query="single", max_results=1)

        assert "## Summary" in result.output
        assert "1 result" in result.output

    @pytest.mark.asyncio
    async def test_metadata_result_count(self):
        t = _tool()
        fake = [
            {"title": "A", "href": "https://a.com", "body": "b"},
            {"title": "B", "href": "https://b.com", "body": "c"},
            {"title": "C", "href": "https://c.com", "body": "d"},
        ]
        ddgs_cls = _mock_ddgs(fake)
        mod = _ddgs_module(ddgs_cls)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await t._run(query="meta test", max_results=3)

        assert result.metadata["result_count"] == 3
