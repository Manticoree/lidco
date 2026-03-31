"""Tests for Q135 RequestModel."""
from __future__ import annotations
import unittest
from lidco.network.request_model import HttpRequest, HttpResponse, RequestBuilder


class TestHttpRequest(unittest.TestCase):
    def test_defaults(self):
        r = HttpRequest()
        self.assertEqual(r.method, "GET")
        self.assertEqual(r.url, "")
        self.assertEqual(r.headers, {})
        self.assertIsNone(r.body)
        self.assertEqual(r.timeout, 30.0)

    def test_custom(self):
        r = HttpRequest(method="POST", url="https://x.com", body='{"a":1}', timeout=5.0)
        self.assertEqual(r.method, "POST")
        self.assertEqual(r.body, '{"a":1}')

    def test_headers_mutable(self):
        r = HttpRequest()
        r.headers["X-Key"] = "val"
        self.assertEqual(r.headers["X-Key"], "val")


class TestHttpResponse(unittest.TestCase):
    def test_defaults(self):
        r = HttpResponse()
        self.assertEqual(r.status_code, 0)
        self.assertEqual(r.body, "")
        self.assertEqual(r.elapsed, 0.0)

    def test_ok_200(self):
        r = HttpResponse(status_code=200)
        self.assertTrue(r.ok)

    def test_ok_299(self):
        r = HttpResponse(status_code=299)
        self.assertTrue(r.ok)

    def test_not_ok_404(self):
        r = HttpResponse(status_code=404)
        self.assertFalse(r.ok)

    def test_not_ok_500(self):
        r = HttpResponse(status_code=500)
        self.assertFalse(r.ok)

    def test_not_ok_199(self):
        r = HttpResponse(status_code=199)
        self.assertFalse(r.ok)


class TestRequestBuilder(unittest.TestCase):
    def test_build_default(self):
        req = RequestBuilder().build()
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.url, "")

    def test_fluent_chain(self):
        req = (
            RequestBuilder()
            .method("POST")
            .url("https://api.example.com")
            .header("X-Key", "abc")
            .body('{"x":1}')
            .timeout(10.0)
            .build()
        )
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.url, "https://api.example.com")
        self.assertEqual(req.headers["X-Key"], "abc")
        self.assertEqual(req.body, '{"x":1}')
        self.assertEqual(req.timeout, 10.0)

    def test_method_uppercased(self):
        req = RequestBuilder().method("post").build()
        self.assertEqual(req.method, "POST")

    def test_get_shortcut(self):
        req = RequestBuilder.get("https://x.com").build()
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.url, "https://x.com")

    def test_post_shortcut(self):
        req = RequestBuilder.post("https://x.com").build()
        self.assertEqual(req.method, "POST")

    def test_put_shortcut(self):
        req = RequestBuilder.put("https://x.com").build()
        self.assertEqual(req.method, "PUT")

    def test_delete_shortcut(self):
        req = RequestBuilder.delete("https://x.com").build()
        self.assertEqual(req.method, "DELETE")

    def test_headers_isolated(self):
        b = RequestBuilder().header("A", "1")
        r1 = b.build()
        r1.headers["B"] = "2"
        r2 = b.build()
        self.assertNotIn("B", r2.headers)

    def test_body_bytes(self):
        req = RequestBuilder().body(b"raw").build()
        self.assertEqual(req.body, b"raw")

    def test_body_none(self):
        req = RequestBuilder().body(None).build()
        self.assertIsNone(req.body)


if __name__ == "__main__":
    unittest.main()
