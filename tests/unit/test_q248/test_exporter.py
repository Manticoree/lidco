"""Tests for ConversationExporter (Q248)."""
from __future__ import annotations

import json
import unittest

from lidco.conversation.exporter import ConversationExporter


def _msgs():
    return [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]


class TestToMarkdown(unittest.TestCase):
    def test_contains_turns(self):
        md = ConversationExporter(_msgs()).to_markdown()
        self.assertIn("Turn 1 (user)", md)
        self.assertIn("Turn 2 (assistant)", md)
        self.assertIn("Hello", md)

    def test_contains_stats(self):
        md = ConversationExporter(_msgs()).to_markdown()
        self.assertIn("Stats", md)
        self.assertIn("Turns: 2", md)

    def test_without_stats(self):
        md = ConversationExporter(_msgs()).with_stats(False).to_markdown()
        self.assertNotIn("Stats", md)

    def test_empty(self):
        md = ConversationExporter([]).to_markdown()
        self.assertIn("Conversation Export", md)


class TestToJson(unittest.TestCase):
    def test_valid_json(self):
        j = ConversationExporter(_msgs()).to_json()
        data = json.loads(j)
        self.assertIn("messages", data)
        self.assertEqual(len(data["messages"]), 2)

    def test_includes_stats(self):
        data = json.loads(ConversationExporter(_msgs()).to_json())
        self.assertIn("stats", data)
        self.assertEqual(data["stats"]["total_turns"], 2)

    def test_without_stats(self):
        data = json.loads(ConversationExporter(_msgs()).with_stats(False).to_json())
        self.assertNotIn("stats", data)

    def test_empty(self):
        data = json.loads(ConversationExporter([]).to_json())
        self.assertEqual(data["messages"], [])


class TestToHtml(unittest.TestCase):
    def test_contains_html_tags(self):
        html = ConversationExporter(_msgs()).to_html()
        self.assertIn("<html>", html)
        self.assertIn("</html>", html)
        self.assertIn("<h2>Turn 1 (user)</h2>", html)

    def test_escapes_html(self):
        msgs = [{"role": "user", "content": "<script>alert(1)</script>"}]
        html = ConversationExporter(msgs).to_html()
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_includes_stats(self):
        html = ConversationExporter(_msgs()).to_html()
        self.assertIn("Stats", html)

    def test_without_stats(self):
        html = ConversationExporter(_msgs()).with_stats(False).to_html()
        self.assertNotIn("Stats", html)


class TestExportDispatch(unittest.TestCase):
    def test_markdown(self):
        result = ConversationExporter(_msgs()).export("markdown")
        self.assertIn("# Conversation Export", result)

    def test_json(self):
        result = ConversationExporter(_msgs()).export("json")
        self.assertIn('"messages"', result)

    def test_html(self):
        result = ConversationExporter(_msgs()).export("html")
        self.assertIn("<html>", result)

    def test_case_insensitive(self):
        result = ConversationExporter(_msgs()).export("JSON")
        self.assertIn('"messages"', result)

    def test_unsupported_format(self):
        with self.assertRaises(ValueError):
            ConversationExporter(_msgs()).export("csv")

    def test_default_markdown(self):
        result = ConversationExporter(_msgs()).export()
        self.assertIn("# Conversation Export", result)


class TestWithStats(unittest.TestCase):
    def test_returns_new_instance(self):
        exp = ConversationExporter(_msgs())
        new = exp.with_stats(False)
        self.assertIsNot(exp, new)
        # original still includes stats
        self.assertIn("Stats", exp.to_markdown())
        self.assertNotIn("Stats", new.to_markdown())


if __name__ == "__main__":
    unittest.main()
