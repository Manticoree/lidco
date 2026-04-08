"""Tests for lidco.apitest.mock_server — task 1694."""

from __future__ import annotations

import json
import time
import unittest
from urllib.request import Request, urlopen

from lidco.apitest.mock_server import (
    MockApiServer,
    MockResponse,
    MockRoute,
    RecordedRequest,
    _match_route,
)


class TestMatchRoute(unittest.TestCase):
    """Test _match_route helper."""

    def test_exact_match(self) -> None:
        route = MockRoute(method="GET", path_pattern="/api/test")
        self.assertTrue(_match_route(route, "GET", "/api/test"))
        self.assertFalse(_match_route(route, "GET", "/api/other"))

    def test_method_mismatch(self) -> None:
        route = MockRoute(method="POST", path_pattern="/api/test")
        self.assertFalse(_match_route(route, "GET", "/api/test"))

    def test_wildcard_method(self) -> None:
        route = MockRoute(method="*", path_pattern="/api/any")
        self.assertTrue(_match_route(route, "GET", "/api/any"))
        self.assertTrue(_match_route(route, "POST", "/api/any"))

    def test_regex_match(self) -> None:
        route = MockRoute(method="GET", path_pattern=r"/api/users/\d+", is_regex=True)
        self.assertTrue(_match_route(route, "GET", "/api/users/123"))
        self.assertFalse(_match_route(route, "GET", "/api/users/abc"))

    def test_case_insensitive_method(self) -> None:
        route = MockRoute(method="GET", path_pattern="/test")
        self.assertTrue(_match_route(route, "get", "/test"))


class TestMockResponse(unittest.TestCase):
    """Test MockResponse frozen dataclass."""

    def test_defaults(self) -> None:
        r = MockResponse()
        self.assertEqual(r.status, 200)
        self.assertIsNone(r.body)
        self.assertEqual(r.headers, {})
        self.assertEqual(r.delay, 0.0)

    def test_custom(self) -> None:
        r = MockResponse(status=404, body={"error": "nope"}, delay=0.1)
        self.assertEqual(r.status, 404)
        self.assertEqual(r.body["error"], "nope")


class TestMockApiServer(unittest.TestCase):
    """Test MockApiServer route matching and management."""

    def test_add_route(self) -> None:
        server = MockApiServer()
        route = MockRoute(method="GET", path_pattern="/hello", response=MockResponse(body="hi"))
        server.add_route(route)
        resp = server.match("GET", "/hello")
        self.assertEqual(resp.body, "hi")

    def test_route_convenience(self) -> None:
        server = MockApiServer()
        server.route("POST", "/create", status=201, body={"created": True})
        resp = server.match("POST", "/create")
        self.assertEqual(resp.status, 201)
        self.assertEqual(resp.body["created"], True)

    def test_fallback(self) -> None:
        server = MockApiServer()
        resp = server.match("GET", "/nope")
        self.assertEqual(resp.status, 404)

    def test_set_fallback(self) -> None:
        server = MockApiServer()
        server.set_fallback(MockResponse(status=503, body="down"))
        resp = server.match("GET", "/any")
        self.assertEqual(resp.status, 503)

    def test_first_match_wins(self) -> None:
        server = MockApiServer()
        server.route("GET", "/x", body="first")
        server.route("GET", "/x", body="second")
        resp = server.match("GET", "/x")
        self.assertEqual(resp.body, "first")

    def test_base_url_without_start(self) -> None:
        server = MockApiServer(host="127.0.0.1", port=9999)
        self.assertEqual(server.base_url, "http://127.0.0.1:9999")


class TestMockApiServerLive(unittest.TestCase):
    """Integration test: start server, make real HTTP requests."""

    def test_start_stop(self) -> None:
        server = MockApiServer(port=0, recording=True)
        server.route("GET", "/ping", body={"pong": True})
        server.start()
        try:
            url = f"{server.base_url}/ping"
            with urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                self.assertEqual(data["pong"], True)

            # Check recording
            self.assertEqual(len(server.recorded_requests), 1)
            self.assertEqual(server.recorded_requests[0].method, "GET")
            self.assertEqual(server.recorded_requests[0].path, "/ping")
        finally:
            server.stop()

    def test_context_manager(self) -> None:
        with MockApiServer(port=0) as server:
            server.route("POST", "/echo", status=201, body={"status": "created"})
            req = Request(
                f"{server.base_url}/echo",
                data=b'{"hello":"world"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 201)
                data = json.loads(resp.read().decode())
                self.assertEqual(data["status"], "created")

    def test_recording_mode(self) -> None:
        with MockApiServer(port=0, recording=True) as server:
            server.route("GET", "/rec", body="ok")
            urlopen(f"{server.base_url}/rec", timeout=5)
            urlopen(f"{server.base_url}/rec", timeout=5)
            self.assertEqual(len(server.recorded_requests), 2)
            server.clear_recorded()
            self.assertEqual(len(server.recorded_requests), 0)

    def test_custom_headers(self) -> None:
        with MockApiServer(port=0) as server:
            server.route("GET", "/h", headers={"X-Custom": "val"}, body="ok")
            with urlopen(f"{server.base_url}/h", timeout=5) as resp:
                self.assertEqual(resp.headers.get("X-Custom"), "val")

    def test_404_fallback(self) -> None:
        with MockApiServer(port=0) as server:
            from urllib.error import HTTPError

            with self.assertRaises(HTTPError) as ctx:
                urlopen(f"{server.base_url}/nonexistent", timeout=5)
            self.assertEqual(ctx.exception.code, 404)

    def test_regex_route(self) -> None:
        with MockApiServer(port=0) as server:
            server.route("GET", r"/users/\d+", body={"found": True}, is_regex=True)
            with urlopen(f"{server.base_url}/users/42", timeout=5) as resp:
                data = json.loads(resp.read().decode())
                self.assertTrue(data["found"])


class TestRecordedRequest(unittest.TestCase):
    """Test RecordedRequest frozen dataclass."""

    def test_creation(self) -> None:
        r = RecordedRequest(
            method="POST",
            path="/api",
            headers={"Content-Type": "application/json"},
            body='{"a":1}',
            timestamp=time.time(),
        )
        self.assertEqual(r.method, "POST")
        self.assertEqual(r.path, "/api")


if __name__ == "__main__":
    unittest.main()
