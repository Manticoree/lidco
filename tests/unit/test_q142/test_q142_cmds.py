"""Tests for Q142 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q142_cmds import register, _state


def _run(coro):
    return asyncio.run(coro)


class TestStreamCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.registry = MagicMock()
        self.registry.register = MagicMock()
        register(self.registry)
        self.handler = self.registry.register.call_args[0][0].handler

    def test_registered(self):
        cmd = self.registry.register.call_args[0][0]
        self.assertEqual(cmd.name, "stream")

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_sub_shows_usage(self):
        result = _run(self.handler("unknown"))
        self.assertIn("Usage", result)

    # --- buffer ---
    def test_buffer_write(self):
        result = _run(self.handler("buffer write hello world"))
        self.assertIn("Buffered", result)

    def test_buffer_read(self):
        _run(self.handler("buffer write line1"))
        result = _run(self.handler("buffer read"))
        self.assertIn("line1", result)

    def test_buffer_read_empty(self):
        result = _run(self.handler("buffer read"))
        self.assertIn("empty", result.lower())

    def test_buffer_new(self):
        _run(self.handler("buffer write first"))
        _run(self.handler("buffer new"))  # consume
        _run(self.handler("buffer write second"))
        result = _run(self.handler("buffer new"))
        self.assertIn("second", result)

    def test_buffer_flush(self):
        _run(self.handler("buffer write x"))
        result = _run(self.handler("buffer flush"))
        self.assertIn("Flushed", result)

    def test_buffer_search(self):
        _run(self.handler("buffer write error: boom"))
        _run(self.handler("buffer write info: ok"))
        result = _run(self.handler("buffer search error"))
        self.assertIn("error", result)

    def test_buffer_clear(self):
        _run(self.handler("buffer write x"))
        result = _run(self.handler("buffer clear"))
        self.assertIn("cleared", result.lower())

    def test_buffer_status(self):
        result = _run(self.handler("buffer status"))
        self.assertIn("Lines", result)

    def test_buffer_unknown_action(self):
        result = _run(self.handler("buffer unknown"))
        self.assertIn("Usage", result)

    # --- tail ---
    def test_tail_add(self):
        result = _run(self.handler("tail add hello"))
        self.assertIn("added", result.lower())

    def test_tail_show(self):
        _run(self.handler("tail add line1"))
        result = _run(self.handler("tail show"))
        self.assertIn("line1", result)

    def test_tail_show_empty(self):
        result = _run(self.handler("tail show"))
        self.assertIn("No lines", result)

    def test_tail_grep(self):
        _run(self.handler("tail add error here"))
        _run(self.handler("tail add info ok"))
        result = _run(self.handler("tail grep error"))
        self.assertIn("error", result)

    def test_tail_followers(self):
        result = _run(self.handler("tail followers"))
        self.assertIn("0", result)

    def test_tail_unknown_action(self):
        result = _run(self.handler("tail unknown"))
        self.assertIn("Usage", result)

    # --- mux ---
    def test_mux_add(self):
        result = _run(self.handler("mux add stdout"))
        self.assertIn("added", result.lower())

    def test_mux_remove(self):
        _run(self.handler("mux add s1"))
        result = _run(self.handler("mux remove s1"))
        self.assertIn("removed", result.lower())

    def test_mux_write(self):
        _run(self.handler("mux add s1"))
        result = _run(self.handler("mux write s1 hello"))
        self.assertIn("Written", result)

    def test_mux_write_unknown(self):
        result = _run(self.handler("mux write nope data"))
        self.assertIn("Unknown stream", result)

    def test_mux_read(self):
        _run(self.handler("mux add s1"))
        _run(self.handler("mux write s1 data"))
        result = _run(self.handler("mux read"))
        self.assertIn("data", result)

    def test_mux_status(self):
        result = _run(self.handler("mux status"))
        self.assertIn("Streams", result)

    def test_mux_unknown_action(self):
        result = _run(self.handler("mux unknown"))
        self.assertIn("Usage", result)

    # --- page ---
    def test_page_load(self):
        result = _run(self.handler("page load line1"))
        self.assertIn("Loaded", result)

    def test_page_show(self):
        _run(self.handler("page load line1"))
        result = _run(self.handler("page show 1"))
        self.assertIn("line1", result)

    def test_page_no_content(self):
        result = _run(self.handler("page show"))
        self.assertIn("No content loaded", result)

    def test_page_next_prev(self):
        lines = "\n".join(f"l{i}" for i in range(50))
        _run(self.handler(f"page load {lines}"))
        result = _run(self.handler("page next"))
        self.assertIn("Page 2", result)
        result = _run(self.handler("page prev"))
        self.assertIn("Page 1", result)

    def test_page_first_last(self):
        lines = "\n".join(f"l{i}" for i in range(50))
        _run(self.handler(f"page load {lines}"))
        result = _run(self.handler("page last"))
        self.assertIn("Page", result)
        result = _run(self.handler("page first"))
        self.assertIn("Page 1", result)

    def test_page_search(self):
        _run(self.handler("page load apple\nbanana\ncherry"))
        result = _run(self.handler("page search banana"))
        self.assertIn("1", result)

    def test_page_status(self):
        _run(self.handler("page load x"))
        result = _run(self.handler("page status"))
        self.assertIn("1/1", result)

    def test_page_unknown_action(self):
        _run(self.handler("page load x"))
        result = _run(self.handler("page unknown"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
