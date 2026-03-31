"""Tests for Q145 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from lidco.cli.commands import q145_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ145Commands(unittest.TestCase):
    def setUp(self):
        q145_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q145_cmds.register(MockRegistry())

    # --- registration ---
    def test_history_registered(self):
        self.assertIn("history", self.registered)

    def test_alias_registered(self):
        self.assertIn("alias", self.registered)

    def test_recent_registered(self):
        self.assertIn("recent", self.registered)

    def test_breadcrumb_registered(self):
        self.assertIn("breadcrumb", self.registered)

    # --- /history ---
    def test_history_no_args(self):
        result = _run(self.registered["history"].handler(""))
        self.assertIn("Usage", result)

    def test_history_search_no_query(self):
        result = _run(self.registered["history"].handler("search"))
        self.assertIn("Usage", result)

    def test_history_search_no_match(self):
        result = _run(self.registered["history"].handler("search zzz"))
        self.assertIn("No history", result)

    def test_history_clear(self):
        result = _run(self.registered["history"].handler("clear"))
        self.assertIn("cleared", result.lower())

    def test_history_last_empty(self):
        result = _run(self.registered["history"].handler("last"))
        self.assertIn("No history", result)

    def test_history_undo_empty(self):
        result = _run(self.registered["history"].handler("undo"))
        self.assertIn("Nothing to undo", result)

    def test_history_frequent_empty(self):
        result = _run(self.registered["history"].handler("frequent"))
        self.assertIn("No history", result)

    # --- /alias ---
    def test_alias_no_args(self):
        result = _run(self.registered["alias"].handler(""))
        self.assertIn("Usage", result)

    def test_alias_add_missing_args(self):
        result = _run(self.registered["alias"].handler("add"))
        self.assertIn("Usage", result)

    def test_alias_add_success(self):
        result = _run(self.registered["alias"].handler("add b /build"))
        self.assertIn("added", result.lower())

    def test_alias_remove_not_found(self):
        result = _run(self.registered["alias"].handler("remove nope"))
        self.assertIn("not found", result.lower())

    def test_alias_list_empty(self):
        result = _run(self.registered["alias"].handler("list"))
        self.assertIn("No aliases", result)

    def test_alias_add_then_list(self):
        _run(self.registered["alias"].handler("add b /build"))
        result = _run(self.registered["alias"].handler("list"))
        self.assertIn("b", result)
        self.assertIn("/build", result)

    def test_alias_remove_success(self):
        _run(self.registered["alias"].handler("add b /build"))
        result = _run(self.registered["alias"].handler("remove b"))
        self.assertIn("removed", result.lower())

    # --- /recent ---
    def test_recent_no_args(self):
        result = _run(self.registered["recent"].handler(""))
        self.assertIn("Usage", result)

    def test_recent_files_empty(self):
        result = _run(self.registered["recent"].handler("files"))
        self.assertIn("No recent", result)

    def test_recent_search_no_pattern(self):
        result = _run(self.registered["recent"].handler("search"))
        self.assertIn("Usage", result)

    def test_recent_search_no_match(self):
        result = _run(self.registered["recent"].handler("search zzz"))
        self.assertIn("No files", result)

    def test_recent_frequent_empty(self):
        result = _run(self.registered["recent"].handler("frequent"))
        self.assertIn("No recent", result)

    def test_recent_clear(self):
        result = _run(self.registered["recent"].handler("clear"))
        self.assertIn("cleared", result.lower())

    # --- /breadcrumb ---
    def test_breadcrumb_no_args(self):
        result = _run(self.registered["breadcrumb"].handler(""))
        self.assertIn("Usage", result)

    def test_breadcrumb_show_empty(self):
        result = _run(self.registered["breadcrumb"].handler("show"))
        self.assertIn("empty", result.lower())

    def test_breadcrumb_push(self):
        result = _run(self.registered["breadcrumb"].handler("push Home"))
        self.assertIn("Pushed", result)

    def test_breadcrumb_push_then_show(self):
        _run(self.registered["breadcrumb"].handler("push Home"))
        _run(self.registered["breadcrumb"].handler("push Project"))
        result = _run(self.registered["breadcrumb"].handler("show"))
        self.assertIn("Home", result)
        self.assertIn("Project", result)

    def test_breadcrumb_back(self):
        _run(self.registered["breadcrumb"].handler("push Home"))
        _run(self.registered["breadcrumb"].handler("push Project"))
        result = _run(self.registered["breadcrumb"].handler("back"))
        self.assertIn("Project", result)

    def test_breadcrumb_back_empty(self):
        result = _run(self.registered["breadcrumb"].handler("back"))
        self.assertIn("Already at the start", result)

    def test_breadcrumb_clear(self):
        _run(self.registered["breadcrumb"].handler("push Home"))
        result = _run(self.registered["breadcrumb"].handler("clear"))
        self.assertIn("cleared", result.lower())

    def test_breadcrumb_push_no_label(self):
        result = _run(self.registered["breadcrumb"].handler("push"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
