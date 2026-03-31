"""Tests for ClipboardManager."""
from __future__ import annotations

import unittest

from lidco.bridge.clipboard import ClipboardManager, ClipboardEntry


class TestClipboardEntry(unittest.TestCase):
    def test_fields(self):
        e = ClipboardEntry(content="hello", timestamp=1.0, source="agent", is_code=False)
        self.assertEqual(e.content, "hello")
        self.assertEqual(e.timestamp, 1.0)
        self.assertEqual(e.source, "agent")
        self.assertFalse(e.is_code)

    def test_code_entry(self):
        e = ClipboardEntry(content="def f(): pass", timestamp=2.0, source="user", is_code=True)
        self.assertTrue(e.is_code)


class TestClipboardManagerCopy(unittest.TestCase):
    def setUp(self):
        self.copied: list[str] = []
        self.cm = ClipboardManager(copy_fn=lambda t: self.copied.append(t))

    def test_copy_stores_in_history(self):
        self.cm.copy("hello")
        hist = self.cm.history()
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0].content, "hello")

    def test_copy_calls_copy_fn(self):
        self.cm.copy("data")
        self.assertEqual(self.copied, ["data"])

    def test_copy_default_source_is_agent(self):
        entry = self.cm.copy("x")
        self.assertEqual(entry.source, "agent")

    def test_copy_custom_source(self):
        entry = self.cm.copy("x", source="user")
        self.assertEqual(entry.source, "user")

    def test_copy_returns_entry(self):
        entry = self.cm.copy("code")
        self.assertIsInstance(entry, ClipboardEntry)

    def test_copy_detects_code(self):
        entry = self.cm.copy("def foo():\n    return 1\n    pass")
        self.assertTrue(entry.is_code)

    def test_copy_detects_non_code(self):
        entry = self.cm.copy("Hello world, how are you?")
        self.assertFalse(entry.is_code)


class TestClipboardManagerPaste(unittest.TestCase):
    def test_paste_calls_paste_fn(self):
        cm = ClipboardManager(paste_fn=lambda: "pasted text")
        self.assertEqual(cm.paste(), "pasted text")

    def test_paste_default_returns_empty(self):
        cm = ClipboardManager()
        self.assertEqual(cm.paste(), "")


class TestClipboardManagerHistory(unittest.TestCase):
    def setUp(self):
        self.cm = ClipboardManager(max_history=5)

    def test_history_empty(self):
        self.assertEqual(self.cm.history(), [])

    def test_history_order_newest_first(self):
        self.cm.copy("a")
        self.cm.copy("b")
        self.cm.copy("c")
        hist = self.cm.history()
        self.assertEqual([e.content for e in hist], ["c", "b", "a"])

    def test_history_limit(self):
        for i in range(5):
            self.cm.copy(f"item{i}")
        hist = self.cm.history(limit=2)
        self.assertEqual(len(hist), 2)

    def test_max_history_eviction(self):
        for i in range(10):
            self.cm.copy(f"item{i}")
        # max_history=5 so oldest entries evicted
        hist = self.cm.history(limit=10)
        self.assertEqual(len(hist), 5)

    def test_clear(self):
        self.cm.copy("a")
        self.cm.copy("b")
        self.cm.clear()
        self.assertEqual(self.cm.history(), [])


class TestDetectCode(unittest.TestCase):
    def test_python_function(self):
        code = "def hello():\n    print('hi')\n    return True"
        self.assertTrue(ClipboardManager.detect_code(code))

    def test_javascript_braces(self):
        code = "function foo() { return bar(); }"
        self.assertTrue(ClipboardManager.detect_code(code))

    def test_plain_text(self):
        self.assertFalse(ClipboardManager.detect_code("Hello, how are you today?"))

    def test_empty_string(self):
        self.assertFalse(ClipboardManager.detect_code(""))

    def test_whitespace_only(self):
        self.assertFalse(ClipboardManager.detect_code("   \n  "))

    def test_indented_block(self):
        code = "if True:\n    x = 1\n    y = 2\n    z = 3"
        self.assertTrue(ClipboardManager.detect_code(code))

    def test_keywords_detection(self):
        code = "import os\nfrom pathlib import Path"
        self.assertTrue(ClipboardManager.detect_code(code))


if __name__ == "__main__":
    unittest.main()
