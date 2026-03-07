"""Tests for web_search and web_fetch tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.base import ToolPermission
from lidco.tools.web_fetch import WebFetchTool, _strip_html
from lidco.tools.web_search import WebSearchTool


class TestWebSearchTool:
    def setup_method(self):
        self.tool = WebSearchTool()

    def test_name(self):
        assert self.tool.name == "web_search"

    def test_permission_is_ask(self):
        assert self.tool.permission == ToolPermission.ASK

    def test_schema(self):
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "web_search"
        props = schema["function"]["parameters"]["properties"]
        assert "query" in props
        assert "max_results" in props

    @pytest.mark.asyncio
    async def test_returns_results(self):
        import sys
        from types import ModuleType

        mock_results = [
            {"title": "Result 1", "href": "https://example.com/1", "body": "Snippet 1"},
            {"title": "Result 2", "href": "https://example.com/2", "body": "Snippet 2"},
        ]
        mock_cls = MagicMock()
        mock_inst = MagicMock()
        mock_inst.text.return_value = mock_results
        mock_cls.return_value.__enter__.return_value = mock_inst
        mock_cls.return_value.__exit__.return_value = None

        mod = ModuleType("duckduckgo_search")
        mod.DDGS = mock_cls  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await self.tool.execute(query="python best practices")

        assert result.success is True
        assert "Result 1" in result.output
        assert "Result 2" in result.output
        assert "https://example.com/1" in result.output

    @pytest.mark.asyncio
    async def test_handles_search_error(self):
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = RuntimeError("Network error")
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"duckduckgo_search": MagicMock(DDGS=lambda: mock_ddgs_instance)}):
            result = await self.tool.execute(query="test query")

        assert result.success is False
        assert "Search failed" in result.error

    @pytest.mark.asyncio
    async def test_no_library_graceful(self):
        """Test graceful handling when duckduckgo-search is not installed."""
        with patch.dict("sys.modules", {"duckduckgo_search": None}):
            result = await self.tool.execute(query="test")

        assert result.success is False
        assert "duckduckgo-search" in result.error


class TestWebFetchTool:
    def setup_method(self):
        self.tool = WebFetchTool()

    def test_name(self):
        assert self.tool.name == "web_fetch"

    def test_permission_is_ask(self):
        assert self.tool.permission == ToolPermission.ASK

    def test_schema(self):
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "web_fetch"
        props = schema["function"]["parameters"]["properties"]
        assert "url" in props
        assert "max_length" in props

    @pytest.mark.asyncio
    async def test_returns_content(self):
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Hello World</p></body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await self.tool.execute(url="https://example.com")

        assert result.success is True
        assert "Hello World" in result.output

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await self.tool.execute(url="https://example.com")

        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_truncates_long_content(self):
        mock_response = MagicMock()
        mock_response.text = "A" * 10000
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await self.tool.execute(url="https://example.com", max_length=100)

        assert result.success is True
        assert "[Truncated]" in result.output
        assert len(result.output) < 200


class TestStripHtml:
    def test_strips_tags(self):
        assert "Hello" in _strip_html("<p>Hello</p>")

    def test_removes_script(self):
        html = "<script>alert('xss')</script><p>Safe</p>"
        result = _strip_html(html)
        assert "alert" not in result
        assert "Safe" in result

    def test_removes_style(self):
        html = "<style>body{color:red}</style><p>Content</p>"
        result = _strip_html(html)
        assert "color" not in result
        assert "Content" in result

    def test_decodes_entities(self):
        html = "&amp; &lt; &gt; &quot;"
        result = _strip_html(html)
        assert "& < > \"" == result
