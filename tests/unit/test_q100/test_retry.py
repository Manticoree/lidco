"""Tests for T635 RetryPolicy and retry decorator."""
import asyncio
import random
from unittest.mock import patch

import pytest

from lidco.core.retry import RetryExhausted, RetryPolicy, retry, retry_async, retry_call


class TestRetryPolicy:
    def test_exponential_backoff(self):
        p = RetryPolicy(base_delay=1.0, backoff="exponential", jitter=False)
        assert p.compute_delay(0) == pytest.approx(1.0)
        assert p.compute_delay(1) == pytest.approx(2.0)
        assert p.compute_delay(2) == pytest.approx(4.0)

    def test_linear_backoff(self):
        p = RetryPolicy(base_delay=2.0, backoff="linear", jitter=False)
        assert p.compute_delay(0) == pytest.approx(2.0)
        assert p.compute_delay(1) == pytest.approx(4.0)
        assert p.compute_delay(2) == pytest.approx(6.0)

    def test_fixed_backoff(self):
        p = RetryPolicy(base_delay=3.0, backoff="fixed", jitter=False)
        assert p.compute_delay(0) == pytest.approx(3.0)
        assert p.compute_delay(5) == pytest.approx(3.0)

    def test_max_delay_clamped(self):
        p = RetryPolicy(base_delay=1.0, backoff="exponential", max_delay=5.0, jitter=False)
        assert p.compute_delay(10) == pytest.approx(5.0)

    def test_jitter_adds_variance(self):
        p = RetryPolicy(base_delay=10.0, backoff="fixed", jitter=True)
        delays = {p.compute_delay(0) for _ in range(20)}
        assert len(delays) > 1  # jitter produces variance


class TestRetryCallSync:
    def test_succeeds_first_try(self):
        fn = lambda: "ok"
        result = retry_call(fn, policy=RetryPolicy(max_attempts=3))
        assert result == "ok"

    def test_retries_on_failure(self):
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("fail")
            return "done"

        with patch("time.sleep"):
            result = retry_call(flaky, policy=RetryPolicy(max_attempts=3, base_delay=0.0))
        assert result == "done"
        assert call_count[0] == 3

    def test_exhausted_raises(self):
        with patch("time.sleep"):
            with pytest.raises(RetryExhausted) as exc_info:
                retry_call(
                    lambda: (_ for _ in ()).throw(RuntimeError("always fails")),
                    policy=RetryPolicy(max_attempts=3, base_delay=0.0),
                )
        assert exc_info.value.stats.attempts == 3

    def test_exhausted_has_last_exception(self):
        with patch("time.sleep"):
            with pytest.raises(RetryExhausted) as exc_info:
                retry_call(
                    lambda: (_ for _ in ()).throw(ValueError("last one")),
                    policy=RetryPolicy(max_attempts=2, base_delay=0.0),
                )
        assert isinstance(exc_info.value.last_exception, ValueError)

    def test_only_catches_specified_exceptions(self):
        p = RetryPolicy(max_attempts=3, base_delay=0.0, exceptions=(ValueError,))
        with pytest.raises(TypeError):
            retry_call(lambda: (_ for _ in ()).throw(TypeError("wrong type")), policy=p)

    def test_retry_call_convenience(self):
        count = [0]

        def fn():
            count[0] += 1
            if count[0] < 2:
                raise RuntimeError("retry me")
            return "success"

        with patch("time.sleep"):
            result = retry_call(fn, policy=RetryPolicy(max_attempts=3, base_delay=0.0))
        assert result == "success"


class TestRetryDecorator:
    def test_decorator_succeeds(self):
        @retry(RetryPolicy(max_attempts=3, base_delay=0.0))
        def fn():
            return "decorated"

        with patch("time.sleep"):
            assert fn() == "decorated"

    def test_decorator_retries(self):
        count = [0]

        @retry(RetryPolicy(max_attempts=3, base_delay=0.0))
        def flaky():
            count[0] += 1
            if count[0] < 3:
                raise RuntimeError("retry")
            return "ok"

        with patch("time.sleep"):
            result = flaky()
        assert result == "ok"
        assert count[0] == 3

    def test_decorator_kwargs_form(self):
        count = [0]

        @retry(max_attempts=2, base_delay=0.0)
        def fn():
            count[0] += 1
            raise RuntimeError("always")

        with patch("time.sleep"):
            with pytest.raises(RetryExhausted):
                fn()
        assert count[0] == 2


class TestRetryAsync:
    def test_async_succeeds(self):
        @retry_async(RetryPolicy(max_attempts=3, base_delay=0.0))
        async def fn():
            return "async_ok"

        with patch("asyncio.sleep", return_value=None):
            result = asyncio.run(fn())
        assert result == "async_ok"

    def test_async_retries_then_succeeds(self):
        count = [0]

        @retry_async(RetryPolicy(max_attempts=3, base_delay=0.0))
        async def flaky():
            count[0] += 1
            if count[0] < 3:
                raise RuntimeError("async fail")
            return "async done"

        async def run():
            with patch("asyncio.sleep", return_value=None):
                return await flaky()

        result = asyncio.run(run())
        assert result == "async done"

    def test_async_exhausted(self):
        @retry_async(RetryPolicy(max_attempts=2, base_delay=0.0))
        async def always_fail():
            raise RuntimeError("always")

        async def run():
            with patch("asyncio.sleep", return_value=None):
                await always_fail()

        with pytest.raises(RetryExhausted):
            asyncio.run(run())
