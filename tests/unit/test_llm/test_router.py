"""Tests for LLM router and base types."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from lidco.llm.base import Message, LLMResponse, BaseLLMProvider
from lidco.llm.router import ModelRouter


class MockProvider(BaseLLMProvider):
    def __init__(self, responses=None, fail_models=None):
        self._responses = responses or {}
        self._fail_models = fail_models or set()
        self.call_log = []

    async def complete(self, messages, *, model=None, **kwargs):
        self.call_log.append(model)
        if model in self._fail_models:
            raise RuntimeError(f"Model {model} unavailable")
        return LLMResponse(
            content=f"Response from {model}",
            model=model or "default",
        )

    async def stream(self, messages, *, model=None, **kwargs):
        if model in self._fail_models:
            raise RuntimeError(f"Model {model} unavailable")
        yield  # pragma: no cover

    def list_models(self):
        return ["model-a", "model-b"]


class TestMessage:
    def test_creation(self):
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.tool_calls == []

    def test_frozen(self):
        msg = Message(role="user", content="hello")
        with pytest.raises(AttributeError):
            msg.content = "changed"


class TestLLMResponse:
    def test_creation(self):
        resp = LLMResponse(content="hi", model="gpt-4")
        assert resp.content == "hi"
        assert resp.model == "gpt-4"
        assert resp.finish_reason == "stop"


class TestModelRouter:
    @pytest.mark.asyncio
    async def test_uses_primary_model(self):
        provider = MockProvider()
        router = ModelRouter(provider, default_model="model-a")
        messages = [Message(role="user", content="hi")]
        result = await router.complete(messages)
        assert result.content == "Response from model-a"

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        provider = MockProvider(fail_models={"model-a"})
        router = ModelRouter(
            provider,
            default_model="model-a",
            fallback_models=["model-b"],
        )
        messages = [Message(role="user", content="hi")]
        result = await router.complete(messages)
        assert result.content == "Response from model-b"
        assert provider.call_log == ["model-a", "model-b"]

    @pytest.mark.asyncio
    async def test_all_models_fail(self):
        provider = MockProvider(fail_models={"model-a", "model-b"})
        router = ModelRouter(
            provider,
            default_model="model-a",
            fallback_models=["model-b"],
        )
        messages = [Message(role="user", content="hi")]
        with pytest.raises(RuntimeError, match="All models failed"):
            await router.complete(messages)

    @pytest.mark.asyncio
    async def test_explicit_model_overrides_default(self):
        provider = MockProvider()
        router = ModelRouter(provider, default_model="model-a")
        messages = [Message(role="user", content="hi")]
        result = await router.complete(messages, model="model-b")
        assert result.content == "Response from model-b"

    def test_list_models(self):
        provider = MockProvider()
        router = ModelRouter(provider, default_model="model-a")
        assert router.list_models() == ["model-a", "model-b"]
