"""Tests for T627 RateLimiter."""
import time
from unittest.mock import patch

import pytest

from lidco.core.rate_limiter import RateLimiter, RateLimiterGroup


class TestRateLimiter:
    def test_acquire_within_capacity(self):
        rl = RateLimiter(rate=10, capacity=10)
        assert rl.acquire(5) is True
        assert rl.available_tokens == pytest.approx(5.0, abs=0.1)

    def test_acquire_exceeds_capacity(self):
        rl = RateLimiter(rate=10, capacity=5)
        assert rl.acquire(6) is False

    def test_acquire_depletes_then_rejects(self):
        rl = RateLimiter(rate=1, capacity=3)
        assert rl.acquire(3) is True
        assert rl.acquire(1) is False

    def test_available_tokens_starts_at_capacity(self):
        rl = RateLimiter(rate=5, capacity=10)
        assert rl.available_tokens == pytest.approx(10.0, abs=0.1)

    def test_reset_restores_capacity(self):
        rl = RateLimiter(rate=1, capacity=5)
        rl.acquire(5)
        assert rl.available_tokens == pytest.approx(0.0, abs=0.1)
        rl.reset()
        assert rl.available_tokens == pytest.approx(5.0, abs=0.1)

    def test_stats_tracks_acquired_rejected(self):
        rl = RateLimiter(rate=10, capacity=3)
        rl.acquire(3)   # success
        rl.acquire(1)   # fail
        s = rl.stats()
        assert s.total_acquired == 1
        assert s.total_rejected == 1

    def test_acquire_wait_timeout_on_empty(self):
        rl = RateLimiter(rate=0.001, capacity=1)
        rl.acquire(1)  # drain
        start = time.monotonic()
        result = rl.acquire_wait(tokens=1, timeout=0.05)
        elapsed = time.monotonic() - start
        assert result is False
        assert elapsed < 0.5  # should not hang

    def test_acquire_wait_succeeds_immediately(self):
        rl = RateLimiter(rate=10, capacity=10)
        assert rl.acquire_wait(tokens=1, timeout=1.0) is True

    def test_invalid_rate_raises(self):
        with pytest.raises(ValueError):
            RateLimiter(rate=0, capacity=10)

    def test_invalid_capacity_raises(self):
        with pytest.raises(ValueError):
            RateLimiter(rate=5, capacity=0)


class TestRateLimiterGroup:
    def test_add_and_acquire(self):
        g = RateLimiterGroup()
        g.add("api", 10, 10)
        assert g.acquire("api") is True

    def test_get_existing(self):
        g = RateLimiterGroup()
        added = g.add("svc", 5, 5)
        assert g.get("svc") is added

    def test_get_nonexistent(self):
        g = RateLimiterGroup()
        assert g.get("nope") is None

    def test_remove(self):
        g = RateLimiterGroup()
        g.add("x", 1, 1)
        assert g.remove("x") is True
        assert g.get("x") is None

    def test_acquire_missing_raises(self):
        g = RateLimiterGroup()
        with pytest.raises(KeyError):
            g.acquire("missing")

    def test_list_limiters(self):
        g = RateLimiterGroup()
        g.add("b", 1, 1)
        g.add("a", 1, 1)
        assert g.list_limiters() == ["a", "b"]
