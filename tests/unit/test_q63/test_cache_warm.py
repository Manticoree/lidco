"""Tests for CacheWarmer — Q63 Task 425."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestWarmResult:
    def test_success_when_no_error(self):
        from lidco.ai.cache_warm import WarmResult
        r = WarmResult(agent_name="coder", tokens_cached=100, duration_ms=50.0)
        assert r.success is True

    def test_not_success_when_error(self):
        from lidco.ai.cache_warm import WarmResult
        r = WarmResult(agent_name="coder", error="connection failed")
        assert r.success is False

    def test_fields(self):
        from lidco.ai.cache_warm import WarmResult
        r = WarmResult(agent_name="tester", tokens_cached=200, duration_ms=100.0)
        assert r.agent_name == "tester"
        assert r.tokens_cached == 200


class TestCacheWarmerNoSession:
    @pytest.mark.asyncio
    async def test_warm_system_prompts_empty_with_no_agents(self):
        from lidco.ai.cache_warm import CacheWarmer
        session = MagicMock()
        session.agent_registry.list_agents.return_value = []
        warmer = CacheWarmer(session)
        results = await warmer.warm_system_prompts()
        assert results == []

    @pytest.mark.asyncio
    async def test_warm_tools_error_when_no_registry(self):
        from lidco.ai.cache_warm import CacheWarmer
        session = MagicMock()
        session.tool_registry = None
        warmer = CacheWarmer(session)
        results = await warmer.warm_tools()
        assert len(results) == 1
        assert results[0].success is False

    @pytest.mark.asyncio
    async def test_warm_system_prompts_agent_not_found(self):
        from lidco.ai.cache_warm import CacheWarmer
        session = MagicMock()
        session.agent_registry.get.return_value = None
        warmer = CacheWarmer(session)
        results = await warmer.warm_system_prompts(["nonexistent"])
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].agent_name == "nonexistent"

    @pytest.mark.asyncio
    async def test_warm_all_returns_combined(self):
        from lidco.ai.cache_warm import CacheWarmer
        session = MagicMock()
        session.agent_registry.list_agents.return_value = []
        session.tool_registry = None
        warmer = CacheWarmer(session)
        results = await warmer.warm_all()
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_warm_tools_no_llm(self):
        from lidco.ai.cache_warm import CacheWarmer
        session = MagicMock()
        session.tool_registry = MagicMock()
        session.tool_registry.list_tools.return_value = [MagicMock()]
        session.llm = None
        warmer = CacheWarmer(session)
        results = await warmer.warm_tools()
        assert len(results) == 1
        assert results[0].success is False
