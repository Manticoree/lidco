"""Tests for APIMockServer (Q256)."""
from __future__ import annotations

import unittest

from lidco.api_intel.extractor import Endpoint
from lidco.api_intel.mock_server import APIMockServer, MockResponse


class TestMockResponse(unittest.TestCase):
    def test_defaults(self):
        r = MockResponse()
        self.assertEqual(r.status, 200)
        self.assertEqual(r.body, {})
        self.assertEqual(r.delay_ms, 0)

    def test_custom(self):
        r = MockResponse(status=404, body={"error": "not found"}, delay_ms=100)
        self.assertEqual(r.status, 404)
        self.assertEqual(r.body["error"], "not found")
        self.assertEqual(r.delay_ms, 100)


class TestAPIMockServer(unittest.TestCase):
    def setUp(self):
        self.server = APIMockServer()

    def test_add_and_get_route(self):
        self.server.add_route("GET", "/items", MockResponse(status=200, body={"items": []}))
        resp = self.server.get_response("GET", "/items")
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.body, {"items": []})

    def test_get_nonexistent(self):
        resp = self.server.get_response("GET", "/nope")
        self.assertIsNone(resp)

    def test_case_insensitive_method(self):
        self.server.add_route("post", "/items", MockResponse(body={"ok": True}))
        resp = self.server.get_response("POST", "/items")
        self.assertIsNotNone(resp)
        self.assertEqual(resp.body, {"ok": True})

    def test_list_routes(self):
        self.server.add_route("GET", "/a", MockResponse())
        self.server.add_route("POST", "/b", MockResponse(status=201))
        routes = self.server.list_routes()
        self.assertEqual(len(routes), 2)
        methods = [r["method"] for r in routes]
        self.assertIn("GET", methods)
        self.assertIn("POST", methods)

    def test_hit_counting(self):
        self.server.add_route("GET", "/x", MockResponse())
        self.server.get_response("GET", "/x")
        self.server.get_response("GET", "/x")
        self.server.get_response("GET", "/x")
        routes = self.server.list_routes()
        route = [r for r in routes if r["path"] == "/x"][0]
        self.assertEqual(route["hits"], 3)

    def test_no_hit_on_miss(self):
        self.server.add_route("GET", "/x", MockResponse())
        self.server.get_response("POST", "/x")  # miss
        routes = self.server.list_routes()
        route = [r for r in routes if r["path"] == "/x"][0]
        self.assertEqual(route["hits"], 0)

    def test_overwrite_route(self):
        self.server.add_route("GET", "/x", MockResponse(status=200))
        self.server.add_route("GET", "/x", MockResponse(status=404))
        resp = self.server.get_response("GET", "/x")
        self.assertEqual(resp.status, 404)


class TestGenerateFromEndpoints(unittest.TestCase):
    def setUp(self):
        self.server = APIMockServer()

    def test_generate(self):
        endpoints = [
            Endpoint(method="GET", path="/items"),
            Endpoint(method="POST", path="/items"),
            Endpoint(method="DELETE", path="/items/{id}"),
        ]
        self.server.generate_from_endpoints(endpoints)
        routes = self.server.list_routes()
        self.assertEqual(len(routes), 3)

    def test_get_body(self):
        endpoints = [Endpoint(method="GET", path="/items")]
        self.server.generate_from_endpoints(endpoints)
        resp = self.server.get_response("GET", "/items")
        self.assertIsNotNone(resp)
        self.assertIn("items", resp.body)

    def test_post_body(self):
        endpoints = [Endpoint(method="POST", path="/items")]
        self.server.generate_from_endpoints(endpoints)
        resp = self.server.get_response("POST", "/items")
        self.assertIn("created", resp.body)

    def test_delete_body(self):
        endpoints = [Endpoint(method="DELETE", path="/items/{id}")]
        self.server.generate_from_endpoints(endpoints)
        resp = self.server.get_response("DELETE", "/items/{id}")
        self.assertIn("deleted", resp.body)


class TestStats(unittest.TestCase):
    def test_empty(self):
        server = APIMockServer()
        s = server.stats()
        self.assertEqual(s["total_routes"], 0)
        self.assertEqual(s["total_hits"], 0)

    def test_with_routes(self):
        server = APIMockServer()
        server.add_route("GET", "/a", MockResponse())
        server.get_response("GET", "/a")
        s = server.stats()
        self.assertEqual(s["total_routes"], 1)
        self.assertEqual(s["total_hits"], 1)
        self.assertEqual(len(s["routes"]), 1)


if __name__ == "__main__":
    unittest.main()
