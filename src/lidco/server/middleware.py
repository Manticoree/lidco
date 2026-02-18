"""Middleware for the LIDCO HTTP server."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Awaitable, Callable

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
