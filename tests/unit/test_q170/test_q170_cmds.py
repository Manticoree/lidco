"""Tests for Q170 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q170_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ170Commands(unittest.TestCase):
    def setUp(self):
        q170_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            last_message = "Last agent response text"

            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        self.mock_registry = MockRegistry()
        q170_cmds.register(self.mock_registry)

    def test_all_commands_registered(self):
        for name in ("copy", "paste", "browse", "clipboard"):
            self.assertIn(name, self.registered, f"/{name} not registered")

    # --- /copy ---

    def test_copy_default(self):
        handler = self.registered["copy"].handler
        result = _run(handler(""))
        self.assertIn("Copied", result)
        self.assertIn("chars", result)

    def test_copy_with_n(self):
        handler = self.registered["copy"].handler
        result = _run(handler("1"))
        self.assertIn("Copied", result)

    def test_copy_bad_n(self):
        handler = self.registered["copy"].handler
        result = _run(handler("abc"))
        self.assertIn("Usage", result)

    # --- /paste ---

    def test_paste_empty(self):
        handler = self.registered["paste"].handler
        result = _run(handler(""))
        self.assertIn("empty", result.lower())

    def test_paste_after_copy(self):
        copy_h = self.registered["copy"].handler
        _run(copy_h(""))
        paste_h = self.registered["paste"].handler
        result = _run(paste_h(""))
        self.assertIn("Pasted", result)

    # --- /browse ---

    def test_browse_no_url(self):
        handler = self.registered["browse"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_browse_success(self):
        from lidco.bridge.page_reader import PageReader
        q170_cmds._state["reader"] = PageReader(
            fetch_fn=lambda u: "<html><title>Test</title><body>Hello</body></html>"
        )
        handler = self.registered["browse"].handler
        result = _run(handler("https://example.com"))
        self.assertIn("Title:", result)
        self.assertIn("Test", result)

    def test_browse_adds_https(self):
        from lidco.bridge.page_reader import PageReader
        q170_cmds._state["reader"] = PageReader(
            fetch_fn=lambda u: f"<html><title>{u}</title><body>OK</body></html>"
        )
        handler = self.registered["browse"].handler
        result = _run(handler("example.com"))
        self.assertIn("https://example.com", result)

    def test_browse_fetch_error(self):
        from lidco.bridge.page_reader import PageReader
        def _fail(url):
            raise ConnectionError("timeout")
        q170_cmds._state["reader"] = PageReader(fetch_fn=_fail)
        handler = self.registered["browse"].handler
        result = _run(handler("https://fail.com"))
        self.assertIn("Failed", result)

    # --- /clipboard ---

    def test_clipboard_empty_history(self):
        handler = self.registered["clipboard"].handler
        result = _run(handler(""))
        self.assertIn("empty", result.lower())

    def test_clipboard_history(self):
        copy_h = self.registered["copy"].handler
        _run(copy_h(""))
        handler = self.registered["clipboard"].handler
        result = _run(handler("history"))
        self.assertIn("Clipboard history", result)

    def test_clipboard_clear(self):
        copy_h = self.registered["copy"].handler
        _run(copy_h(""))
        handler = self.registered["clipboard"].handler
        result = _run(handler("clear"))
        self.assertIn("cleared", result.lower())
        # Verify empty after clear
        result2 = _run(handler("history"))
        self.assertIn("empty", result2.lower())

    def test_clipboard_unknown_sub(self):
        handler = self.registered["clipboard"].handler
        result = _run(handler("xyz"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
