"""Tests for the full LLM retry + fallback chain."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from litellm.exceptions import AuthenticationError, BadRequestError, RateLimitError

from lidco.llm.base import LLMResponse, StreamChunk
from lidco.llm.exceptions import LLMRetryExhausted
from lidco.llm.retry import RetryConfig, with_retry
from lidco.llm.router import ModelRouter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_litellm_error(cls: type, message: str = "error") -> Exception:
    return cls(message=message, model="test-model", llm_provider="openai")


def _make_response(model: str = "primary-model") -> LLMResponse:
    return LLMResponse(
        content="ok",
        model=model,
        tool_calls=[],
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        finish_reason="stop",
        cost_usd=0.0,
    )


def _make_router(
    provider: AsyncMock,
    fallback_models: list[str] | None = None,
) -> ModelRouter:
    return ModelRouter(
        provider=provider,
        default_model="primary-model",
        fallback_models=fallback_models or [],
    )


# ---------------------------------------------------------------------------
# with_retry: LLMRetryExhausted carries model name and original error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_exhausted_exception_carries_model_name() -> None:
    config = RetryConfig(max_retries=1, base_delay=0.0, jitter=False)
    error = _make_litellm_error(RateLimitError)
    fn = AsyncMock(side_effect=error)

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(LLMRetryExhausted) as exc_info:
            await with_retry(fn, config, model_name="my-model")

    exc = exc_info.value
    assert "my-model" in str(exc)
    assert len(exc.attempts) == 1
    assert exc.attempts[0][0] == "my-model"
    assert isinstance(exc.attempts[0][1], RateLimitError)


@pytest.mark.asyncio()
async def test_non_retryable_error_propagates_immediately_from_with_retry() -> None:
    """AuthenticationError should bypass with_retry entirely."""
    config = RetryConfig(max_retries=3, base_delay=0.0, jitter=False)
    error = _make_litellm_error(AuthenticationError)
    fn = AsyncMock(side_effect=error)

    with pytest.raises(AuthenticationError):
        await with_retry(fn, config, model_name="my-model")

    assert fn.await_count == 1


# ---------------------------------------------------------------------------
# ModelRouter.complete: retry then fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_primary_succeeds_on_first_try() -> None:
    """Happy path: provider.complete() returns immediately, no fallback needed."""
    response = _make_response()
    provider = AsyncMock()
    provider.complete.return_value = response

    router = _make_router(provider, fallback_models=["fallback-model"])
    result = await router.complete([])

    assert result.content == "ok"
    # Router called the primary model exactly once
    assert provider.complete.await_count == 1


@pytest.mark.asyncio()
async def test_primary_exhausted_fallback_succeeds() -> None:
    """Primary exhausts all retries; fallback model succeeds."""
    fallback_response = _make_response(model="fallback-model")
    exhausted = LLMRetryExhausted(
        "primary failed", attempts=[("primary-model", Exception("rate limit"))]
    )
    provider = AsyncMock()
    provider.complete.side_effect = [exhausted, fallback_response]

    router = _make_router(provider, fallback_models=["fallback-model"])
    result = await router.complete([])

    assert result.model == "fallback-model"
    assert provider.complete.await_count == 2


@pytest.mark.asyncio()
async def test_all_models_exhausted_raises_llm_retry_exhausted() -> None:
    """Both primary and fallback exhaust retries → LLMRetryExhausted with all attempts."""
    err1 = LLMRetryExhausted("p1", attempts=[("primary-model", Exception("a"))])
    err2 = LLMRetryExhausted("p2", attempts=[("fallback-model", Exception("b"))])
    provider = AsyncMock()
    provider.complete.side_effect = [err1, err2]

    router = _make_router(provider, fallback_models=["fallback-model"])

    with pytest.raises(LLMRetryExhausted) as exc_info:
        await router.complete([])

    exc = exc_info.value
    assert len(exc.attempts) == 2
    model_names = [a[0] for a in exc.attempts]
    assert "primary-model" in model_names
    assert "fallback-model" in model_names


@pytest.mark.asyncio()
async def test_non_retryable_error_propagates_from_router() -> None:
    """BadRequestError is not LLMRetryExhausted — propagates immediately, no fallback."""
    provider = AsyncMock()
    provider.complete.side_effect = _make_litellm_error(BadRequestError)

    router = _make_router(provider, fallback_models=["fallback-model"])

    with pytest.raises(BadRequestError):
        await router.complete([])

    # Fallback NOT attempted
    assert provider.complete.await_count == 1


@pytest.mark.asyncio()
async def test_no_fallback_configured_raises_after_primary() -> None:
    """No fallback models — single-model chain exhausted → LLMRetryExhausted."""
    exhausted = LLMRetryExhausted("fail", attempts=[("primary-model", Exception("x"))])
    provider = AsyncMock()
    provider.complete.side_effect = exhausted

    router = _make_router(provider)  # no fallback

    with pytest.raises(LLMRetryExhausted) as exc_info:
        await router.complete([])

    exc = exc_info.value
    assert len(exc.attempts) == 1


# ---------------------------------------------------------------------------
# ModelRouter.stream: retry then fallback
# ---------------------------------------------------------------------------

async def _async_chunks(*texts: str):
    for t in texts:
        yield StreamChunk(content=t)


@pytest.mark.asyncio()
async def test_stream_primary_exhausted_fallback_succeeds() -> None:
    """Stream: primary fails at connection phase; fallback yields chunks."""
    exhausted = LLMRetryExhausted("stream fail", attempts=[("primary-model", Exception())])

    provider = MagicMock()
    call_count = 0

    async def _stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise exhausted
        async for chunk in _async_chunks("hello", " world"):
            yield chunk

    provider.stream = _stream

    router = _make_router(provider, fallback_models=["fallback-model"])
    chunks = [c async for c in router.stream([])]

    assert [c.content for c in chunks] == ["hello", " world"]
    assert call_count == 2


@pytest.mark.asyncio()
async def test_stream_all_models_exhausted() -> None:
    """Stream: all models fail at connection phase → LLMRetryExhausted."""
    provider = MagicMock()

    async def _stream(*args, **kwargs):
        raise LLMRetryExhausted(
            "stream fail", attempts=[("model", Exception("conn err"))]
        )
        yield  # make it an async generator

    provider.stream = _stream

    router = _make_router(provider, fallback_models=["fallback-model"])

    with pytest.raises(LLMRetryExhausted):
        async for _ in router.stream([]):
            pass


# ---------------------------------------------------------------------------
# Session wires config.llm.retry into LiteLLMProvider
# ---------------------------------------------------------------------------

def test_session_wires_retry_config() -> None:
    """Session passes config.llm.retry values to LiteLLMProvider."""
    from lidco.core.config import LidcoConfig, LLMConfig
    from lidco.core.config import RetryConfig as ConfigRetryConfig
    from lidco.core.session import Session

    cfg = LidcoConfig(
        llm=LLMConfig(
            retry=ConfigRetryConfig(max_retries=7, base_delay=2.5, max_delay=120.0, jitter=False)
        )
    )

    with patch("lidco.core.session.LiteLLMProvider") as MockProvider:
        with patch("lidco.core.session.MemoryStore"):
            with patch("lidco.core.session.ToolRegistry"):
                Session(config=cfg)

    _, kwargs = MockProvider.call_args
    retry_cfg = kwargs["retry_config"]
    assert retry_cfg.max_retries == 7
    assert retry_cfg.base_delay == 2.5
    assert retry_cfg.max_delay == 120.0
    assert retry_cfg.jitter is False
