"""Tests for LLM router and base types."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from lidco.llm.base import Message, LLMResponse, BaseLLMProvider
from lidco.llm.exceptions import LLMRetryExhausted
from lidco.llm.router import ModelRouter


def _make_exhausted(model: str) -> LLMRetryExhausted:
    return LLMRetryExhausted(
        f"Model {model} exhausted retries",
        attempts=[(model, RuntimeError(f"Model {model} unavailable"))],
    )


class MockProvider(BaseLLMProvider):
    def __init__(self, responses=None, fail_models=None, raw_fail_models=None):
        self._responses = responses or {}
        self._fail_models = fail_models or set()
        self._raw_fail_models = raw_fail_models or set()  # raise raw Exception (not LLMRetryExhausted)
        self.call_log = []

    async def complete(self, messages, *, model=None, **kwargs):
        self.call_log.append(model)
        if model in self._fail_models:
            raise _make_exhausted(model)
        return LLMResponse(
            content=f"Response from {model}",
            model=model or "default",
        )

    async def stream(self, messages, *, model=None, **kwargs):
        self.call_log.append(model)
        if model in self._fail_models:
            raise _make_exhausted(model)
        if model in self._raw_fail_models:
            raise AttributeError(f"Malformed chunk from {model}")
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
        resp = LLMResponse(content="hi", model="openai/glm-4.7")
        assert resp.content == "hi"
        assert resp.model == "openai/glm-4.7"
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
        with pytest.raises(LLMRetryExhausted, match="All .* model"):
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


class TestModelRouterStream:
    @pytest.mark.asyncio
    async def test_stream_fallback_on_retry_exhausted(self):
        """Router falls back to next model when primary raises LLMRetryExhausted during stream."""
        chunks_received = []

        class ChunkProvider(BaseLLMProvider):
            def __init__(self):
                self.call_log = []

            async def complete(self, messages, *, model=None, **kwargs):
                return LLMResponse(content="", model=model or "default")

            async def stream(self, messages, *, model=None, **kwargs):
                self.call_log.append(model)
                if model == "model-a":
                    raise _make_exhausted("model-a")
                from lidco.llm.base import StreamChunk
                yield StreamChunk(content="chunk-from-b")

            def list_models(self):
                return []

        provider = ChunkProvider()
        router = ModelRouter(provider, default_model="model-a", fallback_models=["model-b"])
        messages = [Message(role="user", content="hi")]

        async for chunk in router.stream(messages):
            chunks_received.append(chunk)

        assert provider.call_log == ["model-a", "model-b"]
        assert len(chunks_received) == 1
        assert chunks_received[0].content == "chunk-from-b"

    @pytest.mark.asyncio
    async def test_stream_fallback_on_raw_exception(self):
        """Router falls back to next model when primary raises a raw (non-LLMRetryExhausted) exception."""
        chunks_received = []

        class ChunkProvider(BaseLLMProvider):
            def __init__(self):
                self.call_log = []

            async def complete(self, messages, *, model=None, **kwargs):
                return LLMResponse(content="", model=model or "default")

            async def stream(self, messages, *, model=None, **kwargs):
                self.call_log.append(model)
                if model == "model-a":
                    raise AttributeError("Malformed chunk from model-a")
                from lidco.llm.base import StreamChunk
                yield StreamChunk(content="fallback-chunk")

            def list_models(self):
                return []

        provider = ChunkProvider()
        router = ModelRouter(provider, default_model="model-a", fallback_models=["model-b"])
        messages = [Message(role="user", content="hi")]

        async for chunk in router.stream(messages):
            chunks_received.append(chunk)

        assert provider.call_log == ["model-a", "model-b"]
        assert len(chunks_received) == 1
        assert chunks_received[0].content == "fallback-chunk"

    @pytest.mark.asyncio
    async def test_stream_all_fail_raises_retry_exhausted(self):
        """When all models fail during stream, raises LLMRetryExhausted."""
        provider = MockProvider(raw_fail_models={"model-a", "model-b"})
        router = ModelRouter(provider, default_model="model-a", fallback_models=["model-b"])
        messages = [Message(role="user", content="hi")]

        with pytest.raises(LLMRetryExhausted, match="All .* model"):
            async for _ in router.stream(messages):
                pass


class TestFallbackCallback:
    """ModelRouter notifies callback when falling back to a different model."""

    @pytest.mark.asyncio
    async def test_complete_fires_fallback_callback(self):
        from lidco.llm.exceptions import LLMRetryExhausted
        notifications: list[tuple[str, str, str]] = []

        provider = MockProvider(fail_models={"model-a"})
        router = ModelRouter(provider, default_model="model-a", fallback_models=["model-b"])
        router.set_fallback_callback(
            lambda failed, fallback, reason: notifications.append((failed, fallback, reason))
        )
        messages = [Message(role="user", content="hi")]
        await router.complete(messages)

        assert len(notifications) == 1
        failed, fallback, reason = notifications[0]
        assert failed == "model-a"
        assert fallback == "model-b"
        assert "exhausted" in reason

    @pytest.mark.asyncio
    async def test_stream_fires_fallback_callback_on_raw_error(self):
        notifications: list[tuple] = []

        class RawErrorProvider:
            async def complete(self, *a, **kw):
                pass
            async def stream(self, messages, *, model=None, **kw):
                if model == "model-a":
                    raise ConnectionError("network failure")
                from lidco.llm.base import StreamChunk
                yield StreamChunk(content="ok")
            def list_models(self): return []
            def set_default_model(self, m): pass

        router = ModelRouter(RawErrorProvider(), default_model="model-a", fallback_models=["model-b"])
        router.set_fallback_callback(
            lambda f, fb, r: notifications.append((f, fb, r))
        )
        chunks = []
        async for chunk in router.stream([Message(role="user", content="hi")]):
            chunks.append(chunk)

        assert len(notifications) == 1
        assert notifications[0][0] == "model-a"
        assert notifications[0][1] == "model-b"

    @pytest.mark.asyncio
    async def test_no_callback_no_crash(self):
        """Router works fine when no fallback callback is set."""
        provider = MockProvider(fail_models={"model-a"})
        router = ModelRouter(provider, default_model="model-a", fallback_models=["model-b"])
        messages = [Message(role="user", content="hi")]
        result = await router.complete(messages)
        assert result is not None
