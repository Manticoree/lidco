"""Tests for AgentComparator — Task 389."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.comparison import AgentComparator, AgentResult, ComparisonResult


def _make_session(*agent_outputs: str) -> MagicMock:
    """Build a minimal fake session whose orchestrator returns sequential responses."""
    session = MagicMock()
    session.get_full_context.return_value = ""

    responses = [MagicMock(content=out, token_usage=MagicMock(total_tokens=10)) for out in agent_outputs]
    session.orchestrator.handle = AsyncMock(side_effect=responses)
    return session


class TestAgentResult:
    def test_dataclass_fields(self):
        ar = AgentResult(agent_name="coder", response="ok", elapsed=1.5, tokens=42)
        assert ar.agent_name == "coder"
        assert ar.response == "ok"
        assert ar.elapsed == 1.5
        assert ar.tokens == 42
        assert ar.success is True
        assert ar.error == ""

    def test_failure_flag(self):
        ar = AgentResult(agent_name="tester", response="", elapsed=0.1, success=False, error="boom")
        assert not ar.success
        assert ar.error == "boom"


class TestComparisonResult:
    def test_default_best_idx(self):
        r = ComparisonResult()
        assert r.best_idx == 0
        assert r.results == []

    def test_with_results(self):
        ar1 = AgentResult(agent_name="coder", response="A", elapsed=1.0)
        ar2 = AgentResult(agent_name="architect", response="B", elapsed=2.0)
        r = ComparisonResult(results=[ar1, ar2], best_idx=1)
        assert r.best_idx == 1
        assert len(r.results) == 2


class TestAgentComparator:
    @pytest.mark.asyncio
    async def test_run_two_agents(self):
        session = _make_session("response A", "response B")
        comparator = AgentComparator()
        result = await comparator.run("write tests", ["coder", "tester"], session)
        assert len(result.results) == 2
        assert result.results[0].agent_name == "coder"
        assert result.results[0].response == "response A"
        assert result.results[1].agent_name == "tester"
        assert result.results[1].response == "response B"

    @pytest.mark.asyncio
    async def test_run_empty_agents(self):
        session = MagicMock()
        comparator = AgentComparator()
        result = await comparator.run("task", [], session)
        assert result.results == []
        assert result.best_idx == 0

    @pytest.mark.asyncio
    async def test_agent_failure_is_captured(self):
        session = MagicMock()
        session.get_full_context.return_value = ""
        session.orchestrator.handle = AsyncMock(side_effect=RuntimeError("LLM down"))
        comparator = AgentComparator()
        result = await comparator.run("task", ["coder"], session)
        assert len(result.results) == 1
        assert not result.results[0].success
        assert "LLM down" in result.results[0].error

    @pytest.mark.asyncio
    async def test_elapsed_recorded(self):
        session = _make_session("ok")
        comparator = AgentComparator()
        result = await comparator.run("task", ["coder"], session)
        assert result.results[0].elapsed >= 0.0

    @pytest.mark.asyncio
    async def test_tokens_extracted_from_response(self):
        session = MagicMock()
        session.get_full_context.return_value = ""
        resp = MagicMock()
        resp.content = "output"
        resp.token_usage = MagicMock(total_tokens=99)
        session.orchestrator.handle = AsyncMock(return_value=resp)
        comparator = AgentComparator()
        result = await comparator.run("task", ["coder"], session)
        assert result.results[0].tokens == 99

    @pytest.mark.asyncio
    async def test_runs_concurrently(self):
        """Verify all three agents are invoked."""
        session = _make_session("r1", "r2", "r3")
        comparator = AgentComparator()
        result = await comparator.run("task", ["coder", "tester", "architect"], session)
        assert len(result.results) == 3
        assert {r.agent_name for r in result.results} == {"coder", "tester", "architect"}
