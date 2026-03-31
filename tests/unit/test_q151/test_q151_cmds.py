"""Tests for Q151 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest

from lidco.cli.commands import q151_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ151Commands(unittest.TestCase):
    def setUp(self):
        q151_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q151_cmds.register(MockRegistry())
        self.handler = self.registered["merge"].handler

    def test_command_registered(self):
        self.assertIn("merge", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    # --- three-way ---

    def test_three_way_no_args(self):
        result = _run(self.handler("three-way"))
        self.assertIn("Usage", result)

    def test_three_way_invalid_json(self):
        result = _run(self.handler("three-way {bad"))
        self.assertIn("Invalid JSON", result)

    def test_three_way_clean_merge(self):
        data = json.dumps({"base": "a\nb\n", "ours": "a\nX\n", "theirs": "a\nb\n"})
        result = _run(self.handler(f"three-way {data}"))
        self.assertIn("Clean merge", result)

    def test_three_way_conflict(self):
        data = json.dumps({"base": "a\nb\n", "ours": "a\nX\n", "theirs": "a\nY\n"})
        result = _run(self.handler(f"three-way {data}"))
        self.assertIn("conflict", result.lower())

    # --- resolve ---

    def test_resolve_no_args(self):
        result = _run(self.handler("resolve"))
        self.assertIn("Usage", result)

    def test_resolve_invalid_json(self):
        result = _run(self.handler("resolve not_json"))
        self.assertIn("Invalid JSON", result)

    def test_resolve_no_conflicts(self):
        data = json.dumps({"base": "a\n", "ours": "a\n", "theirs": "a\n"})
        result = _run(self.handler(f"resolve {data}"))
        self.assertIn("No conflicts", result)

    def test_resolve_ours(self):
        data = json.dumps({
            "base": "a\nb\n", "ours": "a\nX\n",
            "theirs": "a\nY\n", "strategy": "ours",
        })
        result = _run(self.handler(f"resolve {data}"))
        self.assertIn("Resolved", result)

    def test_resolve_theirs(self):
        data = json.dumps({
            "base": "a\nb\n", "ours": "a\nX\n",
            "theirs": "a\nY\n", "strategy": "theirs",
        })
        result = _run(self.handler(f"resolve {data}"))
        self.assertIn("Resolved", result)

    def test_resolve_both(self):
        data = json.dumps({
            "base": "a\nb\n", "ours": "a\nX\n",
            "theirs": "a\nY\n", "strategy": "both",
        })
        result = _run(self.handler(f"resolve {data}"))
        self.assertIn("Resolved", result)

    # --- stats ---

    def test_stats_no_args(self):
        result = _run(self.handler("stats"))
        self.assertIn("Usage", result)

    def test_stats_invalid_json(self):
        result = _run(self.handler("stats {bad"))
        self.assertIn("Invalid JSON", result)

    def test_stats_compute(self):
        data = json.dumps({"old": "a\n", "new": "b\n", "path": "f.py"})
        result = _run(self.handler(f"stats {data}"))
        self.assertIn("f.py", result)

    def test_stats_no_changes(self):
        data = json.dumps({"old": "a\n", "new": "a\n", "path": "f.py"})
        result = _run(self.handler(f"stats {data}"))
        self.assertIn("no changes", result)

    # --- patch ---

    def test_patch_no_args(self):
        result = _run(self.handler("patch"))
        self.assertIn("Usage", result)

    def test_patch_invalid_json(self):
        result = _run(self.handler("patch oops"))
        self.assertIn("Invalid JSON", result)

    def test_patch_generate(self):
        data = json.dumps({"path": "f.py", "old": "a\n", "new": "b\n"})
        result = _run(self.handler(f"patch {data}"))
        self.assertIn("---", result)
        self.assertIn("+++", result)

    def test_patch_no_diff(self):
        data = json.dumps({"path": "f.py", "old": "same\n", "new": "same\n"})
        result = _run(self.handler(f"patch {data}"))
        self.assertIn("No differences", result)


if __name__ == "__main__":
    unittest.main()
