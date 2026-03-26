"""Tests for T628 CircuitBreaker."""
import time
from unittest.mock import patch

import pytest

from lidco.core.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_successful_call_returns_value(self):
        cb = CircuitBreaker()
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.state == CircuitState.CLOSED

    def test_failure_increments_count(self):
        cb = CircuitBreaker()
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        assert cb.failure_count == 1

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == CircuitState.OPEN

    def test_open_raises_circuit_open_error(self):
        cb = CircuitBreaker(failure_threshold=2)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: "ok")

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        # Next call should transition to HALF_OPEN and attempt fn
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        time.sleep(0.02)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("still failing")))
        assert cb.state == CircuitState.OPEN

    def test_reset_returns_to_closed(self):
        cb = CircuitBreaker(failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_excluded_exceptions_not_counted(self):
        cb = CircuitBreaker(failure_threshold=3, excluded_exceptions=(ValueError,))
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("excluded")))
        assert cb.failure_count == 0

    def test_non_excluded_exception_counted(self):
        cb = CircuitBreaker(failure_threshold=5, excluded_exceptions=(ValueError,))
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("counted")))
        assert cb.failure_count == 1

    def test_stats_reflects_state(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.call(lambda: "ok")
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        s = cb.stats()
        assert s.total_calls == 2
        assert s.total_failures == 1
        assert s.success_count == 1
