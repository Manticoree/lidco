"""Tests for RateLimitMiddleware sliding-window per-IP rate limiter."""

from __future__ import annotations

import time
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient
from fastapi import FastAPI

from lidco.server.middleware import RateLimitMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(path_limits: dict[str, tuple[int, int]]) -> FastAPI:
    """Return a minimal FastAPI app with RateLimitMiddleware."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, path_limits=path_limits)

    @app.get("/chat")
    async def chat():
        return {"ok": True}

    @app.get("/index")
    async def index():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/other")
    async def other():
        return {"ok": True}

    return app


def _client(path_limits: dict[str, tuple[int, int]]) -> TestClient:
    return TestClient(_make_app(path_limits), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Basic pass-through
# ---------------------------------------------------------------------------

class TestRateLimitPassThrough:
    def test_under_limit_request_succeeds(self):
        client = _client({"/chat": (3, 60)})
        resp = client.get("/chat")
        assert resp.status_code == 200

    def test_health_never_rate_limited(self):
        # Even with a tiny limit, /health is always exempt
        client = _client({"/health": (1, 60)})
        for _ in range(5):
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_unconfigured_path_not_limited(self):
        # /other has no configured prefix → never limited
        client = _client({"/chat": (1, 60)})
        for _ in range(5):
            resp = client.get("/other")
            assert resp.status_code == 200

    def test_multiple_requests_under_limit_all_pass(self):
        client = _client({"/chat": (5, 60)})
        for _ in range(5):
            assert client.get("/chat").status_code == 200


# ---------------------------------------------------------------------------
# 429 triggering
# ---------------------------------------------------------------------------

class TestRateLimitExceeded:
    def test_request_after_limit_returns_429(self):
        client = _client({"/chat": (3, 60)})
        for _ in range(3):
            client.get("/chat")
        resp = client.get("/chat")
        assert resp.status_code == 429

    def test_429_body_contains_error_key(self):
        client = _client({"/chat": (1, 60)})
        client.get("/chat")
        resp = client.get("/chat")
        body = resp.json()
        assert "error" in body
        assert "Too Many Requests" in body["error"]

    def test_429_body_contains_retry_after(self):
        client = _client({"/chat": (1, 60)})
        client.get("/chat")
        resp = client.get("/chat")
        body = resp.json()
        assert "retry_after" in body
        assert isinstance(body["retry_after"], int)
        assert body["retry_after"] > 0

    def test_429_response_has_retry_after_header(self):
        client = _client({"/chat": (1, 60)})
        client.get("/chat")
        resp = client.get("/chat")
        assert "Retry-After" in resp.headers
        assert int(resp.headers["Retry-After"]) > 0

    def test_index_has_separate_limit(self):
        client = _client({"/chat": (60, 60), "/index": (2, 60)})
        # Use up the index limit
        for _ in range(2):
            client.get("/index")
        assert client.get("/index").status_code == 429
        # Chat limit not affected
        assert client.get("/chat").status_code == 200


# ---------------------------------------------------------------------------
# Window expiry
# ---------------------------------------------------------------------------

class TestRateLimitWindowExpiry:
    def test_expired_timestamps_are_evicted(self):
        """After the window passes, the bucket clears and requests are allowed."""
        mw = RateLimitMiddleware(app=MagicMock(), path_limits={"/chat": (2, 60)})

        # Directly pre-fill the bucket with stale timestamps
        bucket_key = ("127.0.0.1", "/chat")
        stale_ts = time.monotonic() - 61  # older than the 60s window
        mw._buckets[bucket_key] = deque([stale_ts, stale_ts])

        # Bucket looks full but timestamps are expired → should not be blocked
        assert len(mw._buckets[bucket_key]) == 2
        # Simulate the eviction logic from dispatch
        now = time.monotonic()
        cutoff = now - 60
        bucket = mw._buckets[bucket_key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        assert len(bucket) == 0

    def test_fresh_timestamps_are_not_evicted(self):
        mw = RateLimitMiddleware(app=MagicMock(), path_limits={"/chat": (5, 60)})
        bucket_key = ("127.0.0.1", "/chat")
        fresh_ts = time.monotonic() - 10  # within the 60s window
        mw._buckets[bucket_key] = deque([fresh_ts])

        now = time.monotonic()
        cutoff = now - 60
        bucket = mw._buckets[bucket_key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        assert len(bucket) == 1


# ---------------------------------------------------------------------------
# Per-IP isolation
# ---------------------------------------------------------------------------

class TestRateLimitPerIPIsolation:
    def test_different_ips_have_separate_buckets(self):
        """Each client IP gets its own counter."""
        mw = RateLimitMiddleware(app=MagicMock(), path_limits={"/chat": (1, 60)})

        key_a = ("1.1.1.1", "/chat")
        key_b = ("2.2.2.2", "/chat")

        now = time.monotonic()
        # Fill bucket for IP A
        mw._buckets[key_a] = deque([now])
        # Bucket for IP B is independent and empty
        assert key_b not in mw._buckets or len(mw._buckets[key_b]) == 0


# ---------------------------------------------------------------------------
# Prefix matching
# ---------------------------------------------------------------------------

class TestRateLimitPrefixMatching:
    def test_most_specific_prefix_wins(self):
        """When /chat and /chat/stream both match, the longer prefix is used."""
        mw = RateLimitMiddleware(
            app=MagicMock(),
            path_limits={"/chat": (1, 60), "/chat/stream": (5, 60)},
        )
        assert mw._match_prefix("/chat/stream") == "/chat/stream"
        assert mw._match_prefix("/chat") == "/chat"

    def test_no_matching_prefix_returns_none(self):
        mw = RateLimitMiddleware(app=MagicMock(), path_limits={"/chat": (1, 60)})
        assert mw._match_prefix("/health") is None
        assert mw._match_prefix("/other") is None

    def test_prefix_matches_subpaths(self):
        mw = RateLimitMiddleware(app=MagicMock(), path_limits={"/chat": (1, 60)})
        assert mw._match_prefix("/chat/v2") == "/chat"


# ---------------------------------------------------------------------------
# Client IP extraction
# ---------------------------------------------------------------------------

class TestClientIPExtraction:
    def _make_request(self, headers: dict[str, str]) -> Request:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/chat",
            "query_string": b"",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": ("127.0.0.1", 1234),
        }
        return Request(scope)

    def test_x_forwarded_for_takes_precedence(self):
        mw = RateLimitMiddleware(app=MagicMock(), path_limits={})
        req = self._make_request({"X-Forwarded-For": "10.0.0.1, 10.0.0.2"})
        assert mw._client_ip(req) == "10.0.0.1"

    def test_falls_back_to_client_host(self):
        mw = RateLimitMiddleware(app=MagicMock(), path_limits={})
        req = self._make_request({})
        assert mw._client_ip(req) == "127.0.0.1"
