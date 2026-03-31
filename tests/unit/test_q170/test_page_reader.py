"""Tests for PageReader."""
from __future__ import annotations

import unittest

from lidco.bridge.page_reader import PageReader, PageContent

SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
<h1>Hello World</h1>
<p>This is a paragraph with <b>bold</b> text.</p>
<script>var x = 1;</script>
<style>.foo { color: red; }</style>
<pre>def hello():
    print("hi")</pre>
<code>x = 42</code>
<a href="https://example.com">Example</a>
<a href="/about">About</a>
<a href="#top">Top</a>
<a href="javascript:void(0)">JS Link</a>
</body>
</html>"""


class TestPageReaderRead(unittest.TestCase):
    def setUp(self):
        self.reader = PageReader(fetch_fn=lambda url: SAMPLE_HTML)

    def test_read_returns_page_content(self):
        page = self.reader.read("https://example.com")
        self.assertIsInstance(page, PageContent)

    def test_read_url_stored(self):
        page = self.reader.read("https://example.com")
        self.assertEqual(page.url, "https://example.com")

    def test_read_title(self):
        page = self.reader.read("https://example.com")
        self.assertEqual(page.title, "Test Page")

    def test_read_text_no_tags(self):
        page = self.reader.read("https://example.com")
        self.assertNotIn("<h1>", page.text)
        self.assertNotIn("<script>", page.text)
        self.assertIn("Hello World", page.text)
        self.assertIn("paragraph", page.text)

    def test_read_code_blocks(self):
        page = self.reader.read("https://example.com")
        self.assertTrue(len(page.code_blocks) >= 1)

    def test_read_links(self):
        page = self.reader.read("https://example.com")
        self.assertIn("https://example.com", [l for l in page.links if "example.com" in l])

    def test_read_fetched_at(self):
        page = self.reader.read("https://example.com")
        self.assertGreater(page.fetched_at, 0)


class TestExtractText(unittest.TestCase):
    def test_strips_tags(self):
        text = PageReader.extract_text("<p>Hello <b>world</b></p>")
        self.assertIn("Hello", text)
        self.assertIn("world", text)
        self.assertNotIn("<p>", text)

    def test_strips_script(self):
        text = PageReader.extract_text("<script>alert(1)</script><p>OK</p>")
        self.assertNotIn("alert", text)
        self.assertIn("OK", text)

    def test_strips_style(self):
        text = PageReader.extract_text("<style>.x{}</style><p>Text</p>")
        self.assertNotIn(".x{}", text)

    def test_entities_decoded(self):
        text = PageReader.extract_text("<p>&amp; &lt; &gt;</p>")
        self.assertIn("&", text)
        self.assertIn("<", text)
        self.assertIn(">", text)


class TestExtractCodeBlocks(unittest.TestCase):
    def test_pre_tag(self):
        blocks = PageReader.extract_code_blocks("<pre>code here</pre>")
        self.assertEqual(blocks, ["code here"])

    def test_code_tag(self):
        blocks = PageReader.extract_code_blocks("<code>x = 1</code>")
        self.assertEqual(blocks, ["x = 1"])

    def test_empty_code(self):
        blocks = PageReader.extract_code_blocks("<code>   </code>")
        self.assertEqual(blocks, [])

    def test_nested_tags_stripped(self):
        blocks = PageReader.extract_code_blocks("<pre><span>hello</span></pre>")
        self.assertEqual(blocks, ["hello"])


class TestExtractTitle(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(PageReader.extract_title("<title>My Page</title>"), "My Page")

    def test_missing(self):
        self.assertEqual(PageReader.extract_title("<html><body>Hi</body></html>"), "")

    def test_with_entities(self):
        self.assertEqual(PageReader.extract_title("<title>A &amp; B</title>"), "A & B")


class TestExtractLinks(unittest.TestCase):
    def test_absolute_links(self):
        links = PageReader.extract_links('<a href="https://example.com">E</a>')
        self.assertEqual(links, ["https://example.com"])

    def test_relative_with_base(self):
        links = PageReader.extract_links(
            '<a href="/about">About</a>', base_url="https://example.com"
        )
        self.assertTrue(any("about" in l for l in links))

    def test_hash_links_skipped(self):
        links = PageReader.extract_links('<a href="#section">S</a>')
        self.assertEqual(links, [])

    def test_javascript_links_skipped(self):
        links = PageReader.extract_links('<a href="javascript:void(0)">X</a>')
        self.assertEqual(links, [])


if __name__ == "__main__":
    unittest.main()
