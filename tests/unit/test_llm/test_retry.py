"""Tests for retry with exponential backoff."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from litellm.exceptions import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

from lidco.llm.retry import RetryConfig, with_retry


@pytest.fixture()
def no_jitter_config() -> RetryConfig:
    return RetryConfig(max_retries=3, base_delay=1.0, max_delay=60.0, jitter=False)


@pytest.fixture()
def jitter_config() -> RetryConfig:
    return RetryConfig(max_retries=3, base_delay=1.0, max_delay=60.0, jitter=True)


def _make_litellm_error(cls: type, message: str = "error") -> Exception:
    """Create a litellm exception with the required constructor args."""
    return cls(
        message=message,
        model="test-model",
        llm_provider="openai",
    )


# --- test_no_retry_on_success ---


@pytest.mark.asyncio()
async def test_no_retry_on_success(no_jitter_config: RetryConfig) -> None:
    fn = AsyncMock(return_value="ok")

    result = await with_retry(fn, no_jitter_config)

    assert result == "ok"
    assert fn.await_count == 1


# --- test_retry_on_rate_limit ---


@pytest.mark.asyncio()
async def test_retry_on_rate_limit(no_jitter_config: RetryConfig) -> None:
    error = _make_litellm_error(RateLimitError)
    fn = AsyncMock(side_effect=[error, error, "ok"])

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await with_retry(fn, no_jitter_config)

    assert result == "ok"
    assert fn.await_count == 3
    assert mock_sleep.await_count == 2


# --- test_retry_on_server_error ---


@pytest.mark.asyncio()
async def test_retry_on_server_error(no_jitter_config: RetryConfig) -> None:
    error = _make_litellm_error(InternalServerError)
    fn = AsyncMock(side_effect=[error, "ok"])

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(fn, no_jitter_config)

    assert result == "ok"
    assert fn.await_count == 2


# --- test_retry_on_timeout ---


@pytest.mark.asyncio()
async def test_retry_on_timeout(no_jitter_config: RetryConfig) -> None:
    error = _make_litellm_error(Timeout)
    fn = AsyncMock(side_effect=[error, "ok"])

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(fn, no_jitter_config)

    assert result == "ok"
    assert fn.await_count == 2


# --- test_retry_on_connection_error ---


@pytest.mark.asyncio()
async def test_retry_on_connection_error(no_jitter_config: RetryConfig) -> None:
    error = _make_litellm_error(APIConnectionError)
    fn = AsyncMock(side_effect=[error, "ok"])

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(fn, no_jitter_config)

    assert result == "ok"
    assert fn.await_count == 2


# --- test_retry_on_service_unavailable ---


@pytest.mark.asyncio()
async def test_retry_on_service_unavailable(no_jitter_config: RetryConfig) -> None:
    error = _make_litellm_error(ServiceUnavailableError)
    fn = AsyncMock(side_effect=[error, "ok"])

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(fn, no_jitter_config)

    assert result == "ok"
    assert fn.await_count == 2


# --- test_max_retries_exceeded ---


@pytest.mark.asyncio()
async def test_max_retries_exceeded(no_jitter_config: RetryConfig) -> None:
    error = _make_litellm_error(RateLimitError)
    fn = AsyncMock(side_effect=error)

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RateLimitError):
            await with_retry(fn, no_jitter_config)

    # 1 initial + 3 retries = 4 total
    assert fn.await_count == 4


# --- test_no_retry_on_non_retryable ---


@pytest.mark.asyncio()
async def test_no_retry_on_bad_request(no_jitter_config: RetryConfig) -> None:
    error = _make_litellm_error(BadRequestError)
    fn = AsyncMock(side_effect=error)

    with pytest.raises(BadRequestError):
        await with_retry(fn, no_jitter_config)

    assert fn.await_count == 1


@pytest.mark.asyncio()
async def test_no_retry_on_auth_error(no_jitter_config: RetryConfig) -> None:
    error = _make_litellm_error(AuthenticationError)
    fn = AsyncMock(side_effect=error)

    with pytest.raises(AuthenticationError):
        await with_retry(fn, no_jitter_config)

    assert fn.await_count == 1


# --- test_exponential_backoff_delays ---


@pytest.mark.asyncio()
async def test_exponential_backoff_delays(no_jitter_config: RetryConfig) -> None:
    error = _make_litellm_error(RateLimitError)
    fn = AsyncMock(side_effect=error)

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(RateLimitError):
            await with_retry(fn, no_jitter_config)

    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert delays == [1.0, 2.0, 4.0]


# --- test_max_delay_cap ---


@pytest.mark.asyncio()
async def test_max_delay_cap() -> None:
    config = RetryConfig(max_retries=5, base_delay=10.0, max_delay=30.0, jitter=False)
    error = _make_litellm_error(RateLimitError)
    fn = AsyncMock(side_effect=error)

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(RateLimitError):
            await with_retry(fn, config)

    delays = [call.args[0] for call in mock_sleep.call_args_list]
    # 10, 20, 30(capped), 30(capped), 30(capped)
    assert delays == [10.0, 20.0, 30.0, 30.0, 30.0]


# --- test_jitter ---


@pytest.mark.asyncio()
async def test_jitter_varies_delay(jitter_config: RetryConfig) -> None:
    error = _make_litellm_error(RateLimitError)
    fn = AsyncMock(side_effect=error)

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(RateLimitError):
            await with_retry(fn, jitter_config)

    delays = [call.args[0] for call in mock_sleep.call_args_list]
    # With jitter, delays should be in range [base*0.5, base*1.5] * 2^attempt
    for i, delay in enumerate(delays):
        base = min(1.0 * (2 ** i), 60.0)
        assert base * 0.5 <= delay <= base * 1.5


# --- test_zero_retries ---


@pytest.mark.asyncio()
async def test_zero_retries_raises_immediately() -> None:
    config = RetryConfig(max_retries=0)
    error = _make_litellm_error(RateLimitError)
    fn = AsyncMock(side_effect=error)

    with pytest.raises(RateLimitError):
        await with_retry(fn, config)

    assert fn.await_count == 1


# --- test_stream_retry (integration-style) ---


@pytest.mark.asyncio()
async def test_stream_retry(no_jitter_config: RetryConfig) -> None:
    """Retry wraps the stream initialization, not individual chunks."""
    error = _make_litellm_error(RateLimitError)

    async def fake_stream():
        yield "chunk1"
        yield "chunk2"

    fn = AsyncMock(side_effect=[error, fake_stream()])

    with patch("lidco.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(fn, no_jitter_config)

    chunks = [c async for c in result]
    assert chunks == ["chunk1", "chunk2"]
    assert fn.await_count == 2
