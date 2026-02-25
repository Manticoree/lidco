"""Tests for BaseAgent.build_system_prompt() — dynamic prompt builder."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lidco.agents.base import (
    AgentConfig,
    BaseAgent,
    _CLARIFICATION_HINT,
    _STREAMING_NARRATION_PROMPT,
)
from lidco.tools.registry import ToolRegistry


class _Agent(BaseAgent):
    def get_system_prompt(self) -> str:
        return "base system prompt"


def _make_agent(tools: list[str] | None = None) -> _Agent:
    config = AgentConfig(
        name="test",
        description="test agent",
        system_prompt="base system prompt",
        tools=tools or [],
    )
    llm = MagicMock()
    registry = ToolRegistry()
    return _Agent(config=config, llm=llm, tool_registry=registry)


class TestBuildSystemPromptBase:
    def test_includes_system_prompt(self):
        agent = _make_agent()
        result = agent.build_system_prompt()
        assert "base system prompt" in result

    def test_no_streaming_no_narration_hint(self):
        agent = _make_agent()
        # stream_callback is None by default
        result = agent.build_system_prompt()
        assert _STREAMING_NARRATION_PROMPT not in result

    def test_streaming_adds_narration_hint(self):
        agent = _make_agent()
        agent.set_stream_callback(lambda text: None)
        result = agent.build_system_prompt()
        assert _STREAMING_NARRATION_PROMPT in result

    def test_no_tools_restriction_adds_clarification_hint(self):
        # Empty tools means all tools — includes ask_user
        agent = _make_agent(tools=[])
        result = agent.build_system_prompt()
        assert _CLARIFICATION_HINT in result

    def test_ask_user_in_tools_adds_clarification_hint(self):
        agent = _make_agent(tools=["file_read", "ask_user"])
        result = agent.build_system_prompt()
        assert _CLARIFICATION_HINT in result

    def test_no_ask_user_excludes_clarification_hint(self):
        agent = _make_agent(tools=["file_read", "bash"])
        result = agent.build_system_prompt()
        assert _CLARIFICATION_HINT not in result

    def test_context_appended_when_provided(self):
        agent = _make_agent()
        result = agent.build_system_prompt(context="## Project\nmy project info")
        assert "## Current Context" in result
        assert "my project info" in result

    def test_no_context_section_when_empty(self):
        agent = _make_agent()
        result = agent.build_system_prompt(context="")
        assert "## Current Context" not in result

    def test_context_comes_after_base_prompt(self):
        agent = _make_agent()
        result = agent.build_system_prompt(context="ctx")
        base_idx = result.index("base system prompt")
        ctx_idx = result.index("ctx")
        assert ctx_idx > base_idx

    def test_streaming_narration_comes_before_clarification(self):
        agent = _make_agent(tools=[])
        agent.set_stream_callback(lambda text: None)
        result = agent.build_system_prompt()
        narr_idx = result.index(_STREAMING_NARRATION_PROMPT.strip()[:20])
        clar_idx = result.index(_CLARIFICATION_HINT.strip()[:20])
        assert narr_idx < clar_idx


class TestBuildSystemPromptOverride:
    def test_subclass_can_override(self):
        class CustomAgent(_Agent):
            def build_system_prompt(self, context: str = "") -> str:
                return f"CUSTOM: {super().build_system_prompt(context)}"

        config = AgentConfig(
            name="custom",
            description="custom",
            system_prompt="base",
            tools=["file_read"],
        )
        agent = CustomAgent(config=config, llm=MagicMock(), tool_registry=ToolRegistry())
        result = agent.build_system_prompt(context="ctx")
        assert result.startswith("CUSTOM:")
        assert "base" in result
        assert "ctx" in result

    def test_overridden_method_used_in_run(self):
        """build_system_prompt override is called by run()."""
        called: list[bool] = []

        class TrackingAgent(_Agent):
            def build_system_prompt(self, context: str = "") -> str:
                called.append(True)
                return "tracked prompt"

        from lidco.llm.base import LLMResponse
        llm = MagicMock()
        llm.complete = MagicMock()

        import asyncio

        async def _fake_complete(messages, **kwargs):
            return LLMResponse(content="done", model="test")

        llm.complete = _fake_complete

        config = AgentConfig(
            name="tracking",
            description="tracking",
            system_prompt="original",
            tools=["file_read"],
        )
        agent = TrackingAgent(config=config, llm=llm, tool_registry=ToolRegistry())

        asyncio.run(agent.run("test message"))
        assert called, "build_system_prompt should have been called by run()"
