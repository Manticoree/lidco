"""Tests for lidco.gateway.request_queue."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from lidco.gateway.request_queue import QueuedRequest, RequestQueue


class TestQueuedRequest:
    def test_defaults(self) -> None:
        req = QueuedRequest(id="abc", provider="openai", payload="data")
        assert req.priority == 0
        assert req.retries == 0
        assert req.max_retries == 3
        assert req.timeout == 30.0


class TestRequestQueue:
    def test_enqueue(self) -> None:
        q = RequestQueue()
        req = q.enqueue("openai", "hello")
        assert req.provider == "openai"
        assert req.payload == "hello"
        assert q.size() == 1

    def test_enqueue_full_raises(self) -> None:
        q = RequestQueue(max_size=1)
        q.enqueue("openai", "a")
        with pytest.raises(ValueError, match="Queue full"):
            q.enqueue("openai", "b")

    def test_dequeue_priority_order(self) -> None:
        q = RequestQueue()
        q.enqueue("openai", "low", priority=1)
        q.enqueue("openai", "high", priority=10)
        q.enqueue("openai", "mid", priority=5)
        req = q.dequeue()
        assert req is not None
        assert req.payload == "high"

    def test_dequeue_empty(self) -> None:
        q = RequestQueue()
        assert q.dequeue() is None

    def test_cancel(self) -> None:
        q = RequestQueue()
        req = q.enqueue("openai", "data")
        assert q.cancel(req.id) is True
        assert q.size() == 0
        assert q.cancel(req.id) is False

    def test_retry_increments(self) -> None:
        q = RequestQueue(backoff_base=0.5)
        req = q.enqueue("openai", "data", max_retries=3)
        retried = q.retry(req.id)
        assert retried is not None
        assert retried.retries == 1

    def test_retry_exceeds_max(self) -> None:
        q = RequestQueue()
        req = q.enqueue("openai", "data", max_retries=1)
        q.retry(req.id)  # retries=1, at max
        result = q.retry(req.id)
        assert result is None

    def test_retry_nonexistent(self) -> None:
        q = RequestQueue()
        assert q.retry("nope") is None

    def test_expire_timeouts(self) -> None:
        q = RequestQueue()
        q.enqueue("openai", "data", timeout=0.01)
        time.sleep(0.02)
        expired = q.expire_timeouts()
        assert expired == 1
        assert q.size() == 0

    def test_expire_keeps_valid(self) -> None:
        q = RequestQueue()
        q.enqueue("openai", "data", timeout=60.0)
        expired = q.expire_timeouts()
        assert expired == 0
        assert q.size() == 1

    def test_pending_all(self) -> None:
        q = RequestQueue()
        q.enqueue("openai", "a")
        q.enqueue("anthropic", "b")
        assert len(q.pending()) == 2

    def test_pending_filtered(self) -> None:
        q = RequestQueue()
        q.enqueue("openai", "a")
        q.enqueue("anthropic", "b")
        assert len(q.pending(provider="openai")) == 1

    def test_summary(self) -> None:
        q = RequestQueue(max_size=500)
        q.enqueue("openai", "a")
        q.enqueue("openai", "b")
        s = q.summary()
        assert s["size"] == 2
        assert s["max_size"] == 500
        assert s["providers"]["openai"] == 2
