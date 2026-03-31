"""Tests for Q135 UrlParser."""
from __future__ import annotations
import unittest
from lidco.network.url_parser import UrlParser, ParsedUrl


class TestParsedUrl(unittest.TestCase):
    def test_defaults(self):
        p = ParsedUrl()
        self.assertEqual(p.scheme, "")
        self.assertEqual(p.host, "")
        self.assertIsNone(p.port)
        self.assertEqual(p.path, "")
        self.assertEqual(p.query_params, {})
        self.assertEqual(p.fragment, "")

    def test_frozen(self):
        p = ParsedUrl(scheme="https", host="example.com")
        with self.assertRaises(AttributeError):
            p.scheme = "http"  # type: ignore[misc]


class TestUrlParser(unittest.TestCase):
    def setUp(self):
        self.parser = UrlParser()

    # --- parse ---

    def test_parse_simple(self):
        p = self.parser.parse("https://example.com/path")
        self.assertEqual(p.scheme, "https")
        self.assertEqual(p.host, "example.com")
        self.assertEqual(p.path, "/path")
        self.assertIsNone(p.port)

    def test_parse_with_port(self):
        p = self.parser.parse("http://localhost:8080/api")
        self.assertEqual(p.host, "localhost")
        self.assertEqual(p.port, 8080)
        self.assertEqual(p.path, "/api")

    def test_parse_with_query(self):
        p = self.parser.parse("https://x.com/search?q=hello&lang=en")
        self.assertEqual(p.query_params["q"], "hello")
        self.assertEqual(p.query_params["lang"], "en")

    def test_parse_with_fragment(self):
        p = self.parser.parse("https://docs.com/page#section")
        self.assertEqual(p.fragment, "section")

    def test_parse_empty(self):
        p = self.parser.parse("")
        self.assertEqual(p.scheme, "")
        self.assertEqual(p.host, "")

    def test_parse_no_path(self):
        p = self.parser.parse("https://example.com")
        self.assertEqual(p.host, "example.com")

    def test_parse_complex_query(self):
        p = self.parser.parse("https://a.com/?x=1&y=2&z=3")
        self.assertEqual(len(p.query_params), 3)

    def test_parse_encoded_query(self):
        p = self.parser.parse("https://a.com/?q=hello%20world")
        self.assertEqual(p.query_params["q"], "hello world")

    # --- build ---

    def test_build_simple(self):
        url = self.parser.build("https", "example.com", "/api")
        self.assertEqual(url, "https://example.com/api")

    def test_build_with_port(self):
        url = self.parser.build("http", "localhost", "/", port=3000)
        self.assertIn("localhost:3000", url)

    def test_build_with_query(self):
        url = self.parser.build("https", "x.com", "/s", query_params={"q": "hi"})
        self.assertIn("q=hi", url)

    def test_build_with_fragment(self):
        url = self.parser.build("https", "docs.com", "/p", fragment="top")
        self.assertTrue(url.endswith("#top"))

    def test_build_default_path(self):
        url = self.parser.build("https", "example.com")
        self.assertIn("example.com", url)

    # --- add_query_params ---

    def test_add_query_params_new(self):
        url = self.parser.add_query_params("https://x.com/path", {"a": "1"})
        self.assertIn("a=1", url)

    def test_add_query_params_merge(self):
        url = self.parser.add_query_params("https://x.com/?a=1", {"b": "2"})
        self.assertIn("a=1", url)
        self.assertIn("b=2", url)

    def test_add_query_params_override(self):
        url = self.parser.add_query_params("https://x.com/?a=1", {"a": "99"})
        self.assertIn("a=99", url)
        self.assertNotIn("a=1", url)

    # --- is_valid ---

    def test_is_valid_true(self):
        self.assertTrue(self.parser.is_valid("https://example.com"))

    def test_is_valid_no_scheme(self):
        self.assertFalse(self.parser.is_valid("example.com"))

    def test_is_valid_no_host(self):
        self.assertFalse(self.parser.is_valid("https://"))

    def test_is_valid_empty(self):
        self.assertFalse(self.parser.is_valid(""))


if __name__ == "__main__":
    unittest.main()
