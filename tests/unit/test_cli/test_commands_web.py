"""Tests for /websearch and /webfetch CLI commands (Q32, Task 147)."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


def _make_registry(session: object | None = None) -> CommandRegistry:
    registry = CommandRegistry()
    registry.set_session(session)
    return registry


def _ddgs_module(results: list[dict], *, raise_exc: Exception | None = None) -> ModuleType:
    mock_cls = MagicMock()
    mock_inst = MagicMock()
    if raise_exc is not None:
        mock_inst.text.side_effect = raise_exc
    else:
        mock_inst.text.return_value = results
    mock_cls.return_value.__enter__.return_value = mock_inst
    mock_cls.return_value.__exit__.return_value = None
    mod = ModuleType("duckduckgo_search")
    mod.DDGS = mock_cls  # type: ignore[attr-defined]
    return mod


class TestWebsearchCommand:
    @pytest.mark.asyncio
    async def test_no_arg_returns_usage(self):
        registry = _make_registry()
        cmd = registry.get("websearch")
        assert cmd is not None
        result = await cmd.handler(arg="")
        assert "Usage" in result or "usage" in result.lower()

    @pytest.mark.asyncio
    async def test_whitespace_only_arg_returns_usage(self):
        registry = _make_registry()
        cmd = registry.get("websearch")
        result = await cmd.handler(arg="   ")
        assert "Usage" in result or "usage" in result.lower()

    @pytest.mark.asyncio
    async def test_successful_search_returns_results(self):
        registry = _make_registry()
        cmd = registry.get("websearch")

        fake = [
            {"title": "Python asyncio docs", "href": "https://docs.python.org/asyncio", "body": "Async I/O library"},
            {"title": "asyncio tutorial", "href": "https://realpython.com/asyncio", "body": "Learn asyncio"},
        ]
        mod = _ddgs_module(fake)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await cmd.handler(arg="python asyncio timeout")

        assert "asyncio" in result.lower()
        assert "https://" in result

    @pytest.mark.asyncio
    async def test_results_include_url_hint(self):
        """When results contain URLs, output should hint at /webfetch."""
        registry = _make_registry()
        cmd = registry.get("websearch")

        fake = [{"title": "Docs", "href": "https://example.com/docs", "body": "Documentation"}]
        mod = _ddgs_module(fake)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await cmd.handler(arg="example docs")

        assert "webfetch" in result.lower() or "/webfetch" in result

    @pytest.mark.asyncio
    async def test_duckduckgo_not_installed(self):
        registry = _make_registry()
        cmd = registry.get("websearch")

        # Remove duckduckgo_search from sys.modules so the tool gets ImportError
        saved = sys.modules.pop("duckduckgo_search", "__absent__")
        # Also clear any cached WebSearchTool module that already imported it
        for key in list(sys.modules.keys()):
            if "web_search" in key:
                del sys.modules[key]
        try:
            result = await cmd.handler(arg="some query")
        finally:
            if saved != "__absent__":
                sys.modules["duckduckgo_search"] = saved

        assert result  # non-empty
        assert any(kw in result.lower() for kw in ("install", "not installed", "pip"))

    @pytest.mark.asyncio
    async def test_search_failure_returns_error_message(self):
        registry = _make_registry()
        cmd = registry.get("websearch")

        mod = _ddgs_module([], raise_exc=RuntimeError("network error"))
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await cmd.handler(arg="failing query")

        assert result  # non-empty

    @pytest.mark.asyncio
    async def test_max_results_is_8(self):
        registry = _make_registry()
        cmd = registry.get("websearch")

        call_args: list[int] = []

        def _capture_text(query: str, max_results: int = 5) -> list:
            call_args.append(max_results)
            return []

        mock_cls = MagicMock()
        mock_inst = MagicMock()
        mock_inst.text.side_effect = _capture_text
        mock_cls.return_value.__enter__.return_value = mock_inst
        mock_cls.return_value.__exit__.return_value = None
        mod = ModuleType("duckduckgo_search")
        mod.DDGS = mock_cls  # type: ignore[attr-defined]

        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            await cmd.handler(arg="test max results")

        assert call_args == [8]


class TestWebfetchCommand:
    @pytest.mark.asyncio
    async def test_no_arg_returns_usage(self):
        registry = _make_registry()
        cmd = registry.get("webfetch")
        assert cmd is not None
        result = await cmd.handler(arg="")
        assert "Usage" in result or "usage" in result.lower()

    @pytest.mark.asyncio
    async def test_whitespace_arg_returns_usage(self):
        registry = _make_registry()
        cmd = registry.get("webfetch")
        result = await cmd.handler(arg="  ")
        assert "Usage" in result or "usage" in result.lower()

    @pytest.mark.asyncio
    async def test_successful_fetch_returns_content(self):
        registry = _make_registry()
        cmd = registry.get("webfetch")

        import httpx
        from unittest.mock import patch, AsyncMock as AM

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.text = "Hello, plain text content"

        mock_client = AsyncMock()
        mock_client.get = AM(return_value=mock_resp)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AM(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AM(return_value=None)
            result = await cmd.handler(arg="https://example.com")

        assert result  # non-empty

    @pytest.mark.asyncio
    async def test_httpx_not_installed(self):
        registry = _make_registry()
        cmd = registry.get("webfetch")

        # Reload web_fetch module with httpx missing
        saved_httpx = sys.modules.get("httpx", "__absent__")
        saved_wf = sys.modules.pop("lidco.tools.web_fetch", None)
        sys.modules["httpx"] = None  # type: ignore[assignment]
        try:
            # Clear cached module so it re-imports with httpx=None
            import importlib
            import lidco.tools.web_fetch as wf_mod
            importlib.reload(wf_mod)
            result = await cmd.handler(arg="https://example.com")
        finally:
            if saved_httpx == "__absent__":
                sys.modules.pop("httpx", None)
            else:
                sys.modules["httpx"] = saved_httpx
            if saved_wf is not None:
                sys.modules["lidco.tools.web_fetch"] = saved_wf

        assert result  # non-empty

    @pytest.mark.asyncio
    async def test_commands_registered(self):
        registry = _make_registry()
        assert registry.get("websearch") is not None
        assert registry.get("webfetch") is not None

    @pytest.mark.asyncio
    async def test_no_session_required(self):
        """Both commands work without an active session."""
        registry = _make_registry(session=None)
        ws_cmd = registry.get("websearch")
        wf_cmd = registry.get("webfetch")

        result = await ws_cmd.handler(arg="")
        assert result

        result = await wf_cmd.handler(arg="")
        assert result
