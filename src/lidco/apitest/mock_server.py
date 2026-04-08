"""API Mock Server — task 1694.

Mock API server with route matching, response templates,
delay simulation, and recording mode.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Route / response data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MockResponse:
    """Canned response for a matched route."""

    status: int = 200
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0  # seconds


@dataclass(frozen=True)
class MockRoute:
    """Route matching rule."""

    method: str  # GET, POST, etc. or "*"
    path_pattern: str  # exact path or regex
    response: MockResponse = field(default_factory=MockResponse)
    is_regex: bool = False


@dataclass(frozen=True)
class RecordedRequest:
    """Captured incoming request (recording mode)."""

    method: str
    path: str
    headers: dict[str, str]
    body: str
    timestamp: float


# ---------------------------------------------------------------------------
# Route matcher
# ---------------------------------------------------------------------------

def _match_route(route: MockRoute, method: str, path: str) -> bool:
    if route.method != "*" and route.method.upper() != method.upper():
        return False
    if route.is_regex:
        return bool(re.fullmatch(route.path_pattern, path))
    return route.path_pattern == path


# ---------------------------------------------------------------------------
# Mock server
# ---------------------------------------------------------------------------

class MockApiServer:
    """Lightweight mock HTTP server for API testing."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        recording: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._routes: list[MockRoute] = []
        self._recording = recording
        self._recorded: list[RecordedRequest] = []
        self._server: HTTPServer | None = None
        self._thread: Thread | None = None
        self._fallback: MockResponse = MockResponse(status=404, body={"error": "not found"})
        self._request_handler_factory: Callable[..., Any] | None = None

    # -- route registration -------------------------------------------------

    def add_route(self, route: MockRoute) -> MockApiServer:
        """Return new server reference with added route (immutable list copy)."""
        self._routes = [*self._routes, route]
        return self

    def route(
        self,
        method: str,
        path: str,
        *,
        status: int = 200,
        body: Any = None,
        headers: dict[str, str] | None = None,
        delay: float = 0.0,
        is_regex: bool = False,
    ) -> MockApiServer:
        """Convenience builder for adding a route."""
        resp = MockResponse(status=status, body=body, headers=headers or {}, delay=delay)
        return self.add_route(MockRoute(method=method, path_pattern=path, response=resp, is_regex=is_regex))

    def set_fallback(self, response: MockResponse) -> None:
        self._fallback = response

    # -- recorded requests --------------------------------------------------

    @property
    def recorded_requests(self) -> list[RecordedRequest]:
        return list(self._recorded)

    def clear_recorded(self) -> None:
        self._recorded = []

    # -- match --------------------------------------------------------------

    def match(self, method: str, path: str) -> MockResponse:
        """Find the first matching route or return the fallback."""
        for route in self._routes:
            if _match_route(route, method, path):
                return route.response
        return self._fallback

    # -- server lifecycle ---------------------------------------------------

    @property
    def base_url(self) -> str:
        if self._server is None:
            return f"http://{self._host}:{self._port}"
        return f"http://{self._host}:{self._server.server_address[1]}"

    @property
    def port(self) -> int:
        if self._server is not None:
            return self._server.server_address[1]
        return self._port

    def start(self) -> None:
        """Start the mock server in a background thread."""
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self._handle("GET")

            def do_POST(self) -> None:
                self._handle("POST")

            def do_PUT(self) -> None:
                self._handle("PUT")

            def do_DELETE(self) -> None:
                self._handle("DELETE")

            def do_PATCH(self) -> None:
                self._handle("PATCH")

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                pass  # Suppress default logging

            def _handle(self, method: str) -> None:
                # Read body
                content_length = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(content_length) if content_length else b""
                body_str = body_bytes.decode("utf-8", errors="replace")

                # Record
                if server_ref._recording:
                    req_headers = {k: v for k, v in self.headers.items()}
                    server_ref._recorded = [
                        *server_ref._recorded,
                        RecordedRequest(
                            method=method,
                            path=self.path,
                            headers=req_headers,
                            body=body_str,
                            timestamp=time.time(),
                        ),
                    ]

                # Match & respond
                resp = server_ref.match(method, self.path)
                if resp.delay > 0:
                    time.sleep(resp.delay)

                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    self.send_header(k, v)

                resp_body: bytes = b""
                if resp.body is not None:
                    if isinstance(resp.body, str):
                        resp_body = resp.body.encode("utf-8")
                    else:
                        resp_body = json.dumps(resp.body).encode("utf-8")
                        self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)

        self._server = HTTPServer((self._host, self._port), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the mock server."""
        if self._server is not None:
            self._server.shutdown()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> MockApiServer:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()
