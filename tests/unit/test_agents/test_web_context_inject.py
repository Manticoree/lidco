"""Tests for _build_web_context() pre-planning injection (Q32, Task 146)."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry
from lidco.llm.base import BaseLLMProvider


def _make_orch(web_context_inject: bool = True) -> GraphOrchestrator:
    llm = MagicMock(spec=BaseLLMProvider)
    registry = MagicMock(spec=AgentRegistry)
    registry.list_agents.return_value = []
    orch = GraphOrchestrator(llm=llm, agent_registry=registry)
    orch.set_web_context_inject(web_context_inject)
    return orch


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


class TestBuildWebContext:
    @pytest.mark.asyncio
    async def test_disabled_returns_empty(self):
        orch = _make_orch(web_context_inject=False)
        result = await orch._build_web_context("what is asyncio?")
        assert result == ""

    @pytest.mark.asyncio
    async def test_no_keywords_returns_empty(self):
        orch = _make_orch(web_context_inject=True)
        result = await orch._build_web_context("just some generic text with nothing specific")
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_web_context_section(self):
        orch = _make_orch(web_context_inject=True)
        fake = [
            {"title": "asyncio docs", "href": "https://docs.python.org/asyncio", "body": "Asynchronous I/O"},
            {"title": "asyncio tutorial", "href": "https://realpython.com/asyncio", "body": "Learn asyncio"},
            {"title": "asyncio tips", "href": "https://example.com/asyncio", "body": "Best practices"},
        ]
        mod = _ddgs_module(fake)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await orch._build_web_context("how do I use import asyncio in Python?")

        assert "## Web Context" in result
        assert result  # non-empty

    @pytest.mark.asyncio
    async def test_top_3_results_included(self):
        orch = _make_orch(web_context_inject=True)
        fake = [
            {"title": f"Result {i}", "href": f"https://example.com/{i}", "body": f"Snippet {i}"}
            for i in range(5)
        ]
        mod = _ddgs_module(fake)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await orch._build_web_context("import asyncio tutorial")

        assert "Result 0" in result
        assert "Result 1" in result
        assert "Result 2" in result
        assert "Result 3" not in result
        assert "Result 4" not in result

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self):
        orch = _make_orch(web_context_inject=True)
        mod = _ddgs_module([], raise_exc=RuntimeError("network down"))
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await orch._build_web_context("import asyncio something")

        assert result == ""

    @pytest.mark.asyncio
    async def test_import_pattern_extracts_keyword(self):
        orch = _make_orch(web_context_inject=True)
        fake = [{"title": "requests docs", "href": "https://requests.readthedocs.io", "body": "HTTP library"}]
        mod = _ddgs_module(fake)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            result = await orch._build_web_context("I want to use import requests to fetch data")

        ddgs_inst = mod.DDGS.return_value.__enter__.return_value  # type: ignore[attr-defined]
        assert ddgs_inst.text.call_count >= 1
        assert result  # non-empty since we got results

    @pytest.mark.asyncio
    async def test_duckduckgo_not_installed_returns_empty(self):
        orch = _make_orch(web_context_inject=True)
        # Remove duckduckgo_search from sys.modules if it exists
        saved = sys.modules.pop("duckduckgo_search", "__absent__")
        try:
            result = await orch._build_web_context("import asyncio how does it work")
        finally:
            if saved != "__absent__":
                sys.modules["duckduckgo_search"] = saved
        assert result == ""

    @pytest.mark.asyncio
    async def test_max_two_queries(self):
        orch = _make_orch(web_context_inject=True)
        fake = [{"title": "X", "href": "https://x.com", "body": "y"}]
        mod = _ddgs_module(fake)
        from unittest.mock import patch
        with patch.dict(sys.modules, {"duckduckgo_search": mod}):
            await orch._build_web_context(
                "import numpy import pandas import scipy import torch import tensorflow"
            )

        ddgs_inst = mod.DDGS.return_value.__enter__.return_value  # type: ignore[attr-defined]
        assert ddgs_inst.text.call_count <= 2


class TestWebContextInjectConfig:
    def test_set_web_context_inject_true(self):
        orch = _make_orch()
        orch.set_web_context_inject(True)
        assert orch._web_context_inject_enabled is True

    def test_set_web_context_inject_false(self):
        orch = _make_orch()
        orch.set_web_context_inject(False)
        assert orch._web_context_inject_enabled is False

    def test_default_is_false(self):
        llm = MagicMock(spec=BaseLLMProvider)
        registry = MagicMock(spec=AgentRegistry)
        registry.list_agents.return_value = []
        orch = GraphOrchestrator(llm=llm, agent_registry=registry)
        assert orch._web_context_inject_enabled is False
