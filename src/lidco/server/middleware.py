"""Middleware for the LIDCO HTTP server."""

from __future__ import annotations

import logging
import math
import os
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with timing information."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


class AuthTokenMiddleware(BaseHTTPMiddleware):
    """Optional bearer-token authentication.

    Set the LIDCO_API_TOKEN environment variable to enable.
    If not set, all requests are allowed (local development mode).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        expected_token = os.environ.get("LIDCO_API_TOKEN", "")

        # No token configured — allow all requests
        if not expected_token:
            return await call_next(request)

        # Skip auth only for health check
        if request.url.path == "/health":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "Missing Authorization header"},
                status_code=401,
            )

        token = auth_header[7:]
        if token != expected_token:
            return JSONResponse(
                {"error": "Invalid token"},
                status_code=403,
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-IP rate limiter.

    *path_limits* maps a URL path prefix to ``(max_requests, window_seconds)``.
    Only paths that match a configured prefix are rate-limited; all others are
    passed through unconditionally.  The ``/health`` endpoint is always exempt.

    Example::

        RateLimitMiddleware(app, path_limits={
            "/chat":  (60, 60),   # 60 req/min
            "/index": (10, 60),   # 10 req/min
        })

    Returns HTTP 429 with a ``Retry-After`` header (seconds until the oldest
    in-window request expires) when a client exceeds its limit.
    """

    def __init__(
        self,
        app: Any,
        path_limits: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        super().__init__(app)
        self._path_limits: dict[str, tuple[int, int]] = path_limits or {}
        # {(client_ip, path_prefix): deque[monotonic_timestamp]}
        self._buckets: dict[tuple[str, str], deque[float]] = {}

    def _client_ip(self, request: Request) -> str:
        """Return the best-effort client IP, honouring X-Forwarded-For."""
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _match_prefix(self, path: str) -> str | None:
        """Return the most-specific configured prefix that *path* starts with."""
        best: str | None = None
        for prefix in self._path_limits:
            if path.startswith(prefix):
                if best is None or len(prefix) > len(best):
                    best = prefix
        return best

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Health endpoint is always exempt
        if path == "/health":
            return await call_next(request)

        prefix = self._match_prefix(path)
        if prefix is None:
            return await call_next(request)

        max_requests, window_seconds = self._path_limits[prefix]
        ip = self._client_ip(request)
        bucket_key = (ip, prefix)
        now = time.monotonic()
        cutoff = now - window_seconds

        bucket = self._buckets.setdefault(bucket_key, deque())

        # Evict timestamps that have fallen outside the current window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= max_requests:
            # Time until the oldest request in the window expires
            retry_after = math.ceil(bucket[0] - cutoff)
            logger.warning(
                "Rate limit exceeded: ip=%s path=%s limit=%d/%ds retry_after=%ds",
                ip,
                path,
                max_requests,
                window_seconds,
                retry_after,
            )
            return JSONResponse(
                {"error": "Too Many Requests", "retry_after": retry_after},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        return await call_next(request)
