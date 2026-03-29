"""Tests for WebSearchGrounder (Task 705)."""
import unittest
from unittest.mock import MagicMock, patch

from lidco.search.web_search import SearchResult, WebSearchGrounder


def _mock_search_fn(query, n):
    """Return deterministic mock results."""
    return [
        SearchResult(title=f"Result {i+1}", url=f"https://example.com/{i}", snippet=f"Snippet for {query}")
        for i in range(n)
    ]


class TestSearchWithInjectedFn(unittest.TestCase):
    def test_returns_results(self):
        grounder = WebSearchGrounder(search_fn=_mock_search_fn)
        results = grounder.search("python", n=3)
        self.assertEqual(len(results), 3)

    def test_result_structure(self):
        grounder = WebSearchGrounder(search_fn=_mock_search_fn)
        results = grounder.search("test", n=1)
        self.assertEqual(results[0].title, "Result 1")
        self.assertIn("example.com", results[0].url)
        self.assertIn("test", results[0].snippet)

    def test_default_n_is_5(self):
        calls = []

        def tracking_fn(q, n):
            calls.append(n)
            return _mock_search_fn(q, n)

        grounder = WebSearchGrounder(search_fn=tracking_fn)
        grounder.search("q")
        self.assertEqual(calls[0], 5)

    def test_custom_n(self):
        grounder = WebSearchGrounder(search_fn=_mock_search_fn)
        results = grounder.search("q", n=2)
        self.assertEqual(len(results), 2)

    def test_empty_query(self):
        grounder = WebSearchGrounder(search_fn=_mock_search_fn)
        results = grounder.search("", n=1)
        self.assertEqual(len(results), 1)


class TestSearchErrorHandling(unittest.TestCase):
    def test_search_fn_error_returns_error_result(self):
        def bad_fn(q, n):
            raise RuntimeError("API down")

        grounder = WebSearchGrounder(search_fn=bad_fn)
        results = grounder.search("q")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Error")
        self.assertIn("API down", results[0].snippet)

    def test_no_search_fn_network_error(self):
        grounder = WebSearchGrounder()
        with patch("lidco.search.web_search.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("Network error")
            results = grounder.search("test")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].title, "Error")

    def test_search_fn_returns_empty(self):
        grounder = WebSearchGrounder(search_fn=lambda q, n: [])
        results = grounder.search("q")
        self.assertEqual(results, [])


class TestGroundedPrompt(unittest.TestCase):
    def test_grounded_prompt_structure(self):
        grounder = WebSearchGrounder(search_fn=_mock_search_fn)
        result = grounder.grounded_prompt("python", "Write code", n=2)
        self.assertIn("Web search context:", result)
        self.assertIn("Write code", result)

    def test_grounded_prompt_includes_snippets(self):
        grounder = WebSearchGrounder(search_fn=_mock_search_fn)
        result = grounder.grounded_prompt("test", "base prompt", n=2)
        self.assertIn("Result 1", result)
        self.assertIn("Snippet for test", result)

    def test_grounded_prompt_no_results(self):
        grounder = WebSearchGrounder(search_fn=lambda q, n: [])
        result = grounder.grounded_prompt("q", "base prompt")
        self.assertEqual(result, "base prompt")

    def test_grounded_prompt_default_n(self):
        calls = []

        def tracking_fn(q, n):
            calls.append(n)
            return _mock_search_fn(q, n)

        grounder = WebSearchGrounder(search_fn=tracking_fn)
        grounder.grounded_prompt("q", "prompt")
        self.assertEqual(calls[0], 3)

    def test_grounded_prompt_ends_with_base(self):
        grounder = WebSearchGrounder(search_fn=_mock_search_fn)
        result = grounder.grounded_prompt("q", "MY BASE PROMPT", n=1)
        self.assertTrue(result.endswith("MY BASE PROMPT"))


class TestScrapeDdg(unittest.TestCase):
    def test_scrape_ddg_parses_html(self):
        html = (
            '<a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com">'
            'Example Title</a> <a class="result__snippet">Example snippet text</a>'
        )
        grounder = WebSearchGrounder()
        with patch("lidco.search.web_search.urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = html.encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            results = grounder._scrape_ddg("test", 5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].title, "Example Title")
            self.assertIn("example.com", results[0].url)

    def test_scrape_ddg_limits_results(self):
        block = (
            '<a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fex.com">'
            'Title</a> <a class="result__snippet">Snip</a>'
        )
        html = block * 10
        grounder = WebSearchGrounder()
        with patch("lidco.search.web_search.urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = html.encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            results = grounder._scrape_ddg("test", 3)
            self.assertEqual(len(results), 3)

    def test_scrape_ddg_empty_html(self):
        grounder = WebSearchGrounder()
        with patch("lidco.search.web_search.urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"<html></html>"
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            results = grounder._scrape_ddg("test", 5)
            self.assertEqual(results, [])

    def test_scrape_strips_html_tags(self):
        html = (
            '<a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fex.com">'
            '<b>Bold</b> Title</a> <a class="result__snippet"><b>Bold</b> snip</a>'
        )
        grounder = WebSearchGrounder()
        with patch("lidco.search.web_search.urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = html.encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            results = grounder._scrape_ddg("test", 5)
            self.assertNotIn("<b>", results[0].title)
            self.assertNotIn("<b>", results[0].snippet)


class TestSearchResultDataclass(unittest.TestCase):
    def test_fields(self):
        r = SearchResult(title="T", url="U", snippet="S")
        self.assertEqual(r.title, "T")
        self.assertEqual(r.url, "U")
        self.assertEqual(r.snippet, "S")


class TestGroundedPromptEdgeCases(unittest.TestCase):
    def test_grounded_prompt_with_error_results(self):
        def error_fn(q, n):
            raise ValueError("oops")

        grounder = WebSearchGrounder(search_fn=error_fn)
        result = grounder.grounded_prompt("q", "base")
        # Error results are still included as context
        self.assertIn("Web search context", result)
        self.assertIn("base", result)

    def test_grounded_prompt_multiline_base(self):
        grounder = WebSearchGrounder(search_fn=_mock_search_fn)
        base = "line1\nline2\nline3"
        result = grounder.grounded_prompt("q", base, n=1)
        self.assertTrue(result.endswith(base))
        self.assertIn("Web search context", result)


class TestSearchFnNone(unittest.TestCase):
    def test_search_without_fn_falls_back_to_scrape(self):
        grounder = WebSearchGrounder()
        with patch("lidco.search.web_search.urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"<html></html>"
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            results = grounder.search("test", n=3)
            self.assertEqual(results, [])
            mock_urlopen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
