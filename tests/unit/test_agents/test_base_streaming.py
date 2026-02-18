"""Tests for BaseAgent streaming support."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.base import AgentConfig, BaseAgent, TokenUsage
from lidco.llm.base import BaseLLMProvider, LLMResponse, Message, StreamChunk
from lidco.tools.base import BaseTool, ToolResult
from lidco.tools.registry import ToolRegistry


# ── Helpers ──────────────────────────────────────────────────────────────────


class ConcreteAgent(BaseAgent):
    """Minimal concrete agent for testing."""

    def get_system_prompt(self) -> str:
        return "You are a test agent."


class FakeLLMProvider(BaseLLMProvider):
    """Fake LLM that yields pre-configured stream chunks."""

    def __init__(self, stream_sequences: list[list[StreamChunk]] | None = None):
        self._stream_sequences = stream_sequences or []
        self._call_idx = 0

    async def complete(self, messages, **kwargs) -> LLMResponse:
        raise NotImplementedError("Use stream in these tests")

    async def stream(self, messages, **kwargs) -> AsyncIterator[StreamChunk]:
        if self._call_idx < len(self._stream_sequences):
            chunks = self._stream_sequences[self._call_idx]
            self._call_idx += 1
            for chunk in chunks:
                yield chunk
        else:
            yield StreamChunk(content="fallback", finish_reason="stop")

    def list_models(self) -> list[str]:
        return ["test-model"]


class FakeTool(BaseTool):
    """Fake tool for testing."""

    def __init__(self, name: str = "test_tool"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "A test tool"

    @property
    def parameters(self) -> list:
        return []

    async def _run(self, **kwargs) -> ToolResult:
        return ToolResult(output="tool output", success=True)


def _make_agent(
    stream_sequences: list[list[StreamChunk]],
    tools: list[BaseTool] | None = None,
) -> ConcreteAgent:
    provider = FakeLLMProvider(stream_sequences)
    registry = ToolRegistry()
    for tool in (tools or []):
        registry.register(tool)

    config = AgentConfig(
        name="test",
        description="test agent",
        system_prompt="You are a test agent.",
        model="test-model",
        max_iterations=5,
    )
    return ConcreteAgent(config, provider, registry)


# ── Tests ────────────────────────────────────────────────────────────────────


class TestStreamComplete:
    @pytest.mark.asyncio
    async def test_text_chunks_accumulated(self):
        """Text chunks are accumulated and forwarded to stream callback."""
        chunks = [
            StreamChunk(content="Hello "),
            StreamChunk(content="world"),
            StreamChunk(finish_reason="stop", usage={"total_tokens": 10}),
        ]
        agent = _make_agent([chunks])

        received_text: list[str] = []
        agent.set_stream_callback(lambda t: received_text.append(t))

        response = await agent.run("test message")

        assert response.content == "Hello world"
        assert received_text == ["Hello ", "world"]

    @pytest.mark.asyncio
    async def test_tool_calls_accumulated_from_deltas(self):
        """Tool call deltas are merged by index into complete tool calls."""
        chunks = [
            StreamChunk(tool_calls=[{
                "index": 0,
                "id": "call_1",
                "type": "function",
                "function": {"name": "test_tool", "arguments": '{"ke'},
            }]),
            StreamChunk(tool_calls=[{
                "index": 0,
                "id": None,
                "type": "function",
                "function": {"name": None, "arguments": 'y": "val"}'},
            }]),
            StreamChunk(finish_reason="tool_calls"),
        ]
        # Second call: final text response (no tools)
        final_chunks = [
            StreamChunk(content="Done"),
            StreamChunk(finish_reason="stop"),
        ]
        agent = _make_agent([chunks, final_chunks], tools=[FakeTool()])
        agent.set_stream_callback(lambda t: None)

        response = await agent.run("test")

        assert response.content == "Done"
        assert len(response.tool_calls_made) == 1
        assert response.tool_calls_made[0]["tool"] == "test_tool"

    @pytest.mark.asyncio
    async def test_usage_extracted_from_final_chunk(self):
        """Usage info from the final chunk is captured."""
        chunks = [
            StreamChunk(content="hi"),
            StreamChunk(
                finish_reason="stop",
                usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            ),
        ]
        agent = _make_agent([chunks])
        agent.set_stream_callback(lambda t: None)

        response = await agent.run("test")

        assert response.token_usage.total_tokens == 8

    @pytest.mark.asyncio
    async def test_no_streaming_without_callback(self):
        """Without stream_callback, agent uses complete() (not stream)."""
        provider = MagicMock(spec=BaseLLMProvider)
        provider.complete = AsyncMock(return_value=LLMResponse(
            content="non-streamed",
            model="test",
            usage={"total_tokens": 5},
        ))
        registry = ToolRegistry()
        config = AgentConfig(
            name="test",
            description="test",
            system_prompt="test",
            model="test-model",
        )
        agent = ConcreteAgent(config, provider, registry)
        # No stream_callback set

        response = await agent.run("test")

        assert response.content == "non-streamed"
        provider.complete.assert_called_once()


class TestToolEventCallbacks:
    @pytest.mark.asyncio
    async def test_tool_events_fired(self):
        """Tool event callback is called with start/end for each tool call."""
        chunks = [
            StreamChunk(tool_calls=[{
                "index": 0,
                "id": "call_1",
                "type": "function",
                "function": {"name": "test_tool", "arguments": "{}"},
            }]),
            StreamChunk(finish_reason="tool_calls"),
        ]
        final_chunks = [
            StreamChunk(content="Done"),
            StreamChunk(finish_reason="stop"),
        ]
        agent = _make_agent([chunks, final_chunks], tools=[FakeTool()])
        agent.set_stream_callback(lambda t: None)

        events: list[tuple] = []

        def on_tool_event(event, name, args, result):
            events.append((event, name, result))

        agent.set_tool_event_callback(on_tool_event)

        await agent.run("test")

        assert len(events) == 2
        assert events[0][0] == "start"
        assert events[0][1] == "test_tool"
        assert events[0][2] is None
        assert events[1][0] == "end"
        assert events[1][1] == "test_tool"
        assert events[1][2] is not None
        assert events[1][2].success is True
