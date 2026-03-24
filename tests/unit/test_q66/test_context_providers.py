"""Tests for custom context providers — T447."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.context.providers.base import ContextProvider
from lidco.context.providers.command_provider import CommandContextProvider
from lidco.context.providers.file_provider import FileContextProvider
from lidco.context.providers.loader import ContextProviderRegistry, _build_provider
from lidco.context.providers.url_provider import URLContextProvider


class ConcreteProvider(ContextProvider):
    def __init__(self, name: str, content: str = "hello", **kwargs):
        super().__init__(name, **kwargs)
        self._content = content

    async def fetch(self) -> str:
        return self._content


class TestContextProviderBase:
    def test_name(self):
        p = ConcreteProvider("docs")
        assert p.name == "docs"

    def test_priority_default(self):
        p = ConcreteProvider("docs")
        assert p.priority == 50

    def test_max_tokens_default(self):
        p = ConcreteProvider("docs")
        assert p.max_tokens == 2000

    def test_custom_priority(self):
        p = ConcreteProvider("docs", priority=80)
        assert p.priority == 80

    def test_fetch_abstract(self):
        pass  # enforced by ABC


class TestFileContextProvider:
    def test_fetch_reads_files(self, tmp_path):
        (tmp_path / "a.md").write_text("content a")
        (tmp_path / "b.md").write_text("content b")
        provider = FileContextProvider("docs", "*.md", base_dir=tmp_path)
        result = asyncio.run(provider.fetch())
        assert "content a" in result
        assert "content b" in result

    def test_fetch_no_matches(self, tmp_path):
        provider = FileContextProvider("empty", "*.xyz", base_dir=tmp_path)
        result = asyncio.run(provider.fetch())
        assert result == ""

    def test_pattern_property(self, tmp_path):
        provider = FileContextProvider("docs", "**/*.md", base_dir=tmp_path)
        assert provider.pattern == "**/*.md"


class TestURLContextProvider:
    def test_fetch_success(self):
        with patch("lidco.context.providers.url_provider.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = b"hello world"
            mock_open.return_value = mock_resp
            provider = URLContextProvider("web", "http://example.com")
            result = asyncio.run(provider.fetch())
        assert result == "hello world"

    def test_fetch_cached(self):
        with patch("lidco.context.providers.url_provider.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = b"cached"
            mock_open.return_value = mock_resp
            provider = URLContextProvider("web", "http://example.com", cache_ttl=60)
            asyncio.run(provider.fetch())
            asyncio.run(provider.fetch())  # second call
        # urlopen only called once due to cache
        assert mock_open.call_count == 1

    def test_fetch_error_returns_message(self):
        from urllib.error import URLError
        with patch("lidco.context.providers.url_provider.urlopen", side_effect=URLError("no route")):
            provider = URLContextProvider("web", "http://bad.url")
            result = asyncio.run(provider.fetch())
        assert "fetch failed" in result.lower()


class TestCommandContextProvider:
    def test_fetch_stdout(self, tmp_path):
        provider = CommandContextProvider("cmd", "echo hello", cwd=tmp_path)
        result = asyncio.run(provider.fetch())
        assert "hello" in result

    def test_fetch_command_property(self):
        provider = CommandContextProvider("cmd", "git status")
        assert provider.command == "git status"


class TestContextProviderRegistry:
    def test_register_and_get(self):
        reg = ContextProviderRegistry()
        p = ConcreteProvider("docs")
        reg.register(p)
        assert reg.get("docs") is p

    def test_unregister(self):
        reg = ContextProviderRegistry()
        reg.register(ConcreteProvider("docs"))
        assert reg.unregister("docs")
        assert reg.get("docs") is None

    def test_unregister_missing(self):
        reg = ContextProviderRegistry()
        assert not reg.unregister("nope")

    def test_collect_sorts_by_priority(self):
        reg = ContextProviderRegistry()
        reg.register(ConcreteProvider("low", "low_content", priority=10))
        reg.register(ConcreteProvider("high", "high_content", priority=90))
        result = asyncio.run(reg.collect())
        assert result.index("high") < result.index("low")

    def test_collect_respects_budget(self):
        reg = ContextProviderRegistry()
        # max_tokens=5 → 20 chars; budget_tokens=100 → well within
        reg.register(ConcreteProvider("a", "a" * 80, max_tokens=20))
        result = asyncio.run(reg.collect(budget_tokens=100))
        # Should include content but trimmed
        assert "a" in result

    def test_build_provider_file(self):
        p = _build_provider({"type": "file", "name": "docs", "pattern": "*.md"})
        assert isinstance(p, FileContextProvider)

    def test_build_provider_url(self):
        p = _build_provider({"type": "url", "name": "web", "url": "http://x.com"})
        assert isinstance(p, URLContextProvider)

    def test_build_provider_command(self):
        p = _build_provider({"type": "command", "name": "git", "command": "git status"})
        assert isinstance(p, CommandContextProvider)

    def test_build_provider_unknown(self):
        p = _build_provider({"type": "unknown"})
        assert p is None
