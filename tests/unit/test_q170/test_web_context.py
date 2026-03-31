"""Tests for WebContextProvider."""
from __future__ import annotations

import unittest

from lidco.bridge.page_reader import PageReader, PageContent
from lidco.bridge.web_context import WebContextProvider


FAKE_HTML = "<html><head><title>Fake</title></head><body><p>Content here.</p></body></html>"


class TestWebContextProvider(unittest.TestCase):
    def setUp(self):
        self.reader = PageReader(fetch_fn=lambda url: FAKE_HTML)
        self.wcp = WebContextProvider(self.reader, max_cache=3)

    def test_resolve_mention_single(self):
        results = self.wcp.resolve_mention("Check @https://example.com for info")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://example.com")

    def test_resolve_mention_multiple(self):
        text = "See @https://a.com and @https://b.com"
        results = self.wcp.resolve_mention(text)
        self.assertEqual(len(results), 2)

    def test_resolve_mention_none(self):
        results = self.wcp.resolve_mention("No URLs here")
        self.assertEqual(results, [])

    def test_get_cached_miss(self):
        self.assertIsNone(self.wcp.get_cached("https://missing.com"))

    def test_get_cached_hit(self):
        self.wcp.resolve_mention("@https://cached.com")
        result = self.wcp.get_cached("https://cached.com")
        self.assertIsNotNone(result)
        self.assertEqual(result.url, "https://cached.com")

    def test_inject_context_replaces_url(self):
        prompt = "Read @https://example.com and summarize"
        result = self.wcp.inject_context(prompt)
        self.assertNotIn("@https://example.com", result)
        self.assertIn("[Web:", result)

    def test_inject_context_no_urls(self):
        prompt = "Just a normal prompt"
        self.assertEqual(self.wcp.inject_context(prompt), prompt)

    def test_clear_cache(self):
        self.wcp.resolve_mention("@https://example.com")
        self.wcp.clear_cache()
        self.assertIsNone(self.wcp.get_cached("https://example.com"))

    def test_lru_eviction(self):
        # max_cache=3, add 4 urls
        for i in range(4):
            self.wcp.resolve_mention(f"@https://site{i}.com")
        # First one should be evicted
        self.assertIsNone(self.wcp.get_cached("https://site0.com"))
        # Last one should be present
        self.assertIsNotNone(self.wcp.get_cached("https://site3.com"))

    def test_cache_reuse(self):
        fetch_count = [0]
        original_fn = self.reader._fetch_fn

        def counting_fetch(url):
            fetch_count[0] += 1
            return original_fn(url)

        self.reader._fetch_fn = counting_fetch
        self.wcp.resolve_mention("@https://example.com")
        self.wcp.resolve_mention("@https://example.com")
        self.assertEqual(fetch_count[0], 1)  # only fetched once


if __name__ == "__main__":
    unittest.main()
