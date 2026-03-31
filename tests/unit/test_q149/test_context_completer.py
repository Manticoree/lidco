"""Tests for ContextCompleter."""
from __future__ import annotations
import unittest
from lidco.completion.context_completer import ContextCompleter, CompletionItem


class TestCompletionItem(unittest.TestCase):
    def test_defaults(self):
        item = CompletionItem(text="foo", category="command", score=1.0)
        self.assertEqual(item.description, "")

    def test_with_description(self):
        item = CompletionItem(text="bar", category="file", score=0.5, description="a file")
        self.assertEqual(item.description, "a file")


class TestContextCompleter(unittest.TestCase):
    def setUp(self):
        self.completer = ContextCompleter()

    # --- add_source / sources ---

    def test_add_source(self):
        self.completer.add_source("command", ["help", "history"])
        self.assertIn("command", self.completer.sources)

    def test_sources_empty(self):
        self.assertEqual(self.completer.sources, [])

    def test_add_source_with_descriptions(self):
        self.completer.add_source("command", ["help"], descriptions={"help": "Show help"})
        items = self.completer.complete("/help")
        found = [i for i in items if "help" in i.text.lower()]
        self.assertTrue(len(found) > 0)

    # --- complete ---

    def test_complete_empty_input(self):
        self.completer.add_source("symbol", ["abc"])
        self.assertEqual(self.completer.complete(""), [])

    def test_complete_whitespace_input(self):
        self.completer.add_source("symbol", ["abc"])
        self.assertEqual(self.completer.complete("   "), [])

    def test_complete_general(self):
        self.completer.add_source("symbol", ["apple", "app", "banana"])
        results = self.completer.complete("app")
        texts = [r.text for r in results]
        self.assertIn("app", texts)
        self.assertIn("apple", texts)

    def test_complete_cursor_pos(self):
        self.completer.add_source("symbol", ["hello", "help"])
        results = self.completer.complete("hel world", cursor_pos=3)
        texts = [r.text for r in results]
        self.assertIn("hello", texts)

    def test_complete_no_match(self):
        self.completer.add_source("symbol", ["abc"])
        self.assertEqual(self.completer.complete("xyz"), [])

    def test_complete_sorted_by_score(self):
        self.completer.add_source("symbol", ["test", "testing", "tester"])
        results = self.completer.complete("test")
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    # --- complete_command ---

    def test_complete_command_prefix(self):
        self.completer.add_source("command", ["help", "history", "halt"])
        results = self.completer.complete_command("/hel")
        texts = [r.text for r in results]
        self.assertIn("/help", texts)

    def test_complete_command_no_source(self):
        results = self.completer.complete_command("/foo")
        self.assertEqual(results, [])

    def test_complete_command_with_slash_in_input(self):
        self.completer.add_source("command", ["help"])
        results = self.completer.complete("/help")
        self.assertTrue(any(r.category == "command" for r in results))

    # --- complete_path ---

    def test_complete_path_source(self):
        self.completer.add_source("file", ["src/main.py", "src/utils.py"])
        results = self.completer.complete_path("src/")
        texts = [r.text for r in results]
        self.assertIn("src/main.py", texts)

    def test_complete_path_no_source(self):
        results = self.completer.complete_path("src/")
        self.assertEqual(results, [])

    def test_complete_path_detected(self):
        self.completer.add_source("file", ["./README.md"])
        results = self.completer.complete("./READ")
        texts = [r.text for r in results]
        self.assertIn("./README.md", texts)

    # --- remove_source ---

    def test_remove_source(self):
        self.completer.add_source("command", ["help"])
        self.completer.remove_source("command")
        self.assertNotIn("command", self.completer.sources)

    def test_remove_source_nonexistent(self):
        self.completer.remove_source("nope")  # should not raise

    # --- multiple sources ---

    def test_multiple_sources_merged(self):
        self.completer.add_source("command", ["test"])
        self.completer.add_source("symbol", ["testfunc"])
        results = self.completer.complete("test")
        categories = {r.category for r in results}
        self.assertTrue(len(categories) >= 1)


if __name__ == "__main__":
    unittest.main()
