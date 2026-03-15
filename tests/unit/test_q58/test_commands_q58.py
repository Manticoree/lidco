"""Tests for Q58 slash commands — Tasks 391, 392."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


def _make_agent_mock(name: str, description: str) -> MagicMock:
    """Create a mock agent with a properly specced _config."""
    agent = MagicMock()
    agent.name = name
    agent.description = description
    cfg = MagicMock()
    cfg.name = name
    cfg.description = description
    cfg.model = "gpt-4"
    cfg.temperature = 0.1
    cfg.max_iterations = 10
    cfg.tools = []
    cfg.disallowed_tools = []
    cfg.permission_mode = None
    cfg.isolation = "none"
    cfg.memory = "project"
    cfg.routing_keywords = []
    agent._config = cfg
    return agent


def _make_registry_with_session() -> tuple[CommandRegistry, MagicMock]:
    registry = CommandRegistry()
    session = MagicMock()
    session.get_full_context.return_value = ""

    agent1 = _make_agent_mock("coder", "writes code")
    agent2 = _make_agent_mock("tester", "writes tests")

    ag_reg = MagicMock()
    ag_reg.list_agents.return_value = [agent1, agent2]
    ag_reg.get.return_value = agent1
    session.agent_registry = ag_reg

    # background_tasks: stub running_count
    bg = MagicMock()
    bg.running_count.return_value = 0
    session.background_tasks = bg

    resp = MagicMock(content="agent response")
    session.orchestrator.handle = AsyncMock(return_value=resp)
    registry.set_session(session)
    return registry, session


class TestBroadcastCommand:
    @pytest.mark.asyncio
    async def test_broadcast_no_message_returns_usage(self):
        registry, _ = _make_registry_with_session()
        cmd = registry.get("broadcast")
        assert cmd is not None
        result = await cmd.handler(arg="")
        assert "Usage" in result

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_agents(self):
        registry, session = _make_registry_with_session()
        cmd = registry.get("broadcast")
        result = await cmd.handler(arg="review auth.py")
        # orchestrator.handle called for each agent
        assert session.orchestrator.handle.call_count == 2

    @pytest.mark.asyncio
    async def test_broadcast_with_agents_flag(self):
        registry, session = _make_registry_with_session()
        cmd = registry.get("broadcast")
        result = await cmd.handler(arg="--agents coder review auth.py")
        assert session.orchestrator.handle.call_count == 1

    @pytest.mark.asyncio
    async def test_broadcast_no_session_returns_error(self):
        registry = CommandRegistry()
        cmd = registry.get("broadcast")
        result = await cmd.handler(arg="hello")
        assert "Session" in result or "not initialized" in result.lower()

    @pytest.mark.asyncio
    async def test_broadcast_deduplicates_bullet_findings(self):
        registry, session = _make_registry_with_session()
        # Both agents return the same finding
        resp = MagicMock(content="- Use dependency injection\n- Always write tests")
        session.orchestrator.handle = AsyncMock(return_value=resp)
        cmd = registry.get("broadcast")
        result = await cmd.handler(arg="review")
        # "Use dependency injection" should appear only once
        assert result.count("Use dependency injection") == 1


class TestAgentsStatsCommand:
    @pytest.mark.asyncio
    async def test_agents_stats_empty(self):
        registry, _ = _make_registry_with_session()
        cmd = registry.get("agents")
        assert cmd is not None
        result = await cmd.handler(arg="stats")
        assert "No agent stats" in result

    @pytest.mark.asyncio
    async def test_agents_stats_with_data(self):
        registry, _ = _make_registry_with_session()
        registry._agent_stats = {
            "coder": {"call_count": 5, "total_elapsed": 10.0, "total_tokens": 500, "success_count": 4},
            "tester": {"call_count": 2, "total_elapsed": 4.0, "total_tokens": 200, "success_count": 2},
        }
        cmd = registry.get("agents")
        result = await cmd.handler(arg="stats")
        assert "coder" in result
        assert "tester" in result
        assert "Leaderboard" in result

    @pytest.mark.asyncio
    async def test_agents_stats_sorted_by_call_count(self):
        registry, _ = _make_registry_with_session()
        registry._agent_stats = {
            "low": {"call_count": 1, "total_elapsed": 1.0, "total_tokens": 10, "success_count": 1},
            "high": {"call_count": 10, "total_elapsed": 20.0, "total_tokens": 1000, "success_count": 8},
        }
        cmd = registry.get("agents")
        result = await cmd.handler(arg="stats")
        high_pos = result.index("high")
        low_pos = result.index("low")
        assert high_pos < low_pos  # high calls comes first

    @pytest.mark.asyncio
    async def test_agents_normal_list_still_works(self):
        registry, _ = _make_registry_with_session()
        cmd = registry.get("agents")
        result = await cmd.handler(arg="")
        assert "coder" in result
        assert "tester" in result

    @pytest.mark.asyncio
    async def test_agents_stats_period_flag_accepted(self):
        registry, _ = _make_registry_with_session()
        registry._agent_stats = {
            "coder": {"call_count": 3, "total_elapsed": 5.0, "total_tokens": 100, "success_count": 3},
        }
        cmd = registry.get("agents")
        result = await cmd.handler(arg="stats --period 7d")
        assert "coder" in result


class TestCompareCommand:
    @pytest.mark.asyncio
    async def test_compare_no_task_returns_usage(self):
        registry, _ = _make_registry_with_session()
        cmd = registry.get("compare")
        assert cmd is not None
        result = await cmd.handler(arg="")
        assert "Usage" in result

    @pytest.mark.asyncio
    async def test_compare_runs_with_agents_flag(self):
        registry, session = _make_registry_with_session()
        cmd = registry.get("compare")
        result = await cmd.handler(arg="--agents coder,tester write tests")
        assert "Comparison" in result

    @pytest.mark.asyncio
    async def test_compare_no_session(self):
        registry = CommandRegistry()
        cmd = registry.get("compare")
        result = await cmd.handler(arg="write tests for auth module")
        assert "Session" in result or "not initialized" in result.lower()


class TestPipelineCommand:
    @pytest.mark.asyncio
    async def test_pipeline_no_arg_returns_usage(self):
        registry, _ = _make_registry_with_session()
        cmd = registry.get("pipeline")
        assert cmd is not None
        result = await cmd.handler(arg="")
        assert "Usage" in result

    @pytest.mark.asyncio
    async def test_pipeline_resume_when_no_state(self):
        registry, _ = _make_registry_with_session()
        cmd = registry.get("pipeline")
        result = await cmd.handler(arg="resume")
        assert "No paused pipeline" in result

    @pytest.mark.asyncio
    async def test_pipeline_missing_file(self):
        registry, _ = _make_registry_with_session()
        cmd = registry.get("pipeline")
        result = await cmd.handler(arg="nonexistent.yaml")
        assert "not found" in result.lower() or "yaml" in result.lower()
