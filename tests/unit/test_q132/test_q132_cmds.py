"""Tests for Q132 CLI commands."""
from __future__ import annotations
import asyncio
import json
import unittest
from lidco.cli.commands import q132_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ132Commands(unittest.TestCase):
    def setUp(self):
        q132_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q132_cmds.register(MockRegistry())
        self.handler = self.registered["fs"].handler

    def test_command_registered(self):
        self.assertIn("fs", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("unknown"))
        self.assertIn("Usage", result)

    # --- classify ---

    def test_classify_basic(self):
        paths = json.dumps(["main.py", "README.md"])
        result = _run(self.handler(f"classify {paths}"))
        self.assertIn("main.py", result)
        self.assertIn("source", result)

    def test_classify_invalid_json(self):
        result = _run(self.handler("classify {bad}"))
        self.assertIn("Invalid JSON", result)

    def test_classify_missing_args(self):
        result = _run(self.handler("classify"))
        self.assertIn("Usage", result)

    def test_classify_shows_language_stats(self):
        paths = json.dumps(["a.py", "b.py", "c.js"])
        result = _run(self.handler(f"classify {paths}"))
        self.assertIn("Language stats", result)

    # --- walk ---

    def test_walk_invalid_path(self):
        result = _run(self.handler("walk /nonexistent/path/xyz"))
        # should handle gracefully
        self.assertTrue("Walk" in result or "error" in result.lower() or "Files:" in result)

    def test_walk_missing_args(self):
        result = _run(self.handler("walk"))
        self.assertIn("Usage", result)

    # --- dupes ---

    def test_dupes_basic(self):
        files = json.dumps({"a.py": "same content", "b.py": "same content"})
        result = _run(self.handler(f"dupes {files}"))
        self.assertIn("Duplicate groups", result)

    def test_dupes_no_dupes(self):
        files = json.dumps({"a.py": "unique a", "b.py": "unique b"})
        result = _run(self.handler(f"dupes {files}"))
        self.assertIn("0", result)

    def test_dupes_invalid_json(self):
        result = _run(self.handler("dupes {bad}"))
        self.assertIn("Invalid JSON", result)

    def test_dupes_missing_args(self):
        result = _run(self.handler("dupes"))
        self.assertIn("Usage", result)

    def test_dupes_shows_wasted_bytes(self):
        files = json.dumps({"a.py": "abc", "b.py": "abc"})
        result = _run(self.handler(f"dupes {files}"))
        self.assertIn("Wasted bytes", result)

    # --- ignore ---

    def test_ignore_basic(self):
        paths = json.dumps(["a.py", "b.log"])
        result = _run(self.handler(f"ignore *.log {paths}"))
        self.assertIn("Kept", result)

    def test_ignore_missing_args(self):
        result = _run(self.handler("ignore"))
        self.assertIn("Usage", result)

    def test_ignore_invalid_json(self):
        result = _run(self.handler("ignore *.log {bad}"))
        self.assertIn("Invalid JSON", result)

    def test_ignore_shows_count(self):
        paths = json.dumps(["a.py", "b.log", "c.log"])
        result = _run(self.handler(f"ignore *.log {paths}"))
        self.assertIn("1 of 3", result)

    def test_command_description(self):
        self.assertIn("Q132", self.registered["fs"].description)


if __name__ == "__main__":
    unittest.main()
