"""Tests for Q146 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q146_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ146Commands(unittest.TestCase):
    def setUp(self):
        q146_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q146_cmds.register(MockRegistry())
        self.handler = self.registered["edit"].handler

    def test_command_registered(self):
        self.assertIn("edit", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    def test_undo_empty(self):
        result = _run(self.handler("undo"))
        self.assertIn("Nothing to undo", result)

    def test_redo_empty(self):
        result = _run(self.handler("redo"))
        self.assertIn("Nothing to redo", result)

    def test_preview_empty(self):
        result = _run(self.handler("preview"))
        self.assertIn("Nothing to preview", result)

    def test_status_empty(self):
        result = _run(self.handler("status"))
        self.assertIn("Undo depth: 0", result)
        self.assertIn("Redo depth: 0", result)

    def test_diff_no_pipe(self):
        result = _run(self.handler("diff hello"))
        self.assertIn("Usage", result)

    def test_diff_no_change(self):
        result = _run(self.handler("diff same|same"))
        self.assertIn("No changes", result)

    def test_diff_with_change(self):
        result = _run(self.handler("diff old line|new line"))
        # Should contain diff markers
        self.assertTrue(len(result) > 0)

    def test_status_shows_label_after_push(self):
        from lidco.editing.edit_transaction import EditTransaction
        from lidco.editing.undo_stack import UndoStack

        stack = UndoStack()
        q146_cmds._state["stack"] = stack
        # Force re-create editor with existing stack
        q146_cmds._state.pop("editor", None)
        tx = EditTransaction(label="test edit")
        tx.add("f.py", "modify", "a", "b")
        stack.push(tx)

        result = _run(self.handler("status"))
        self.assertIn("Undo depth: 1", result)
        self.assertIn("test edit", result)

    def test_edit_description(self):
        cmd = self.registered["edit"]
        self.assertIn("Q146", cmd.description)

    def test_status_after_state_reset(self):
        q146_cmds._state.clear()
        result = _run(self.handler("status"))
        self.assertIn("Undo depth: 0", result)

    def test_diff_multiline(self):
        # pipe-separated old|new
        result = _run(self.handler("diff a|b"))
        self.assertTrue(len(result) > 0)

    def test_preview_with_data(self):
        from lidco.editing.edit_transaction import EditTransaction
        from lidco.editing.undo_stack import UndoStack

        stack = UndoStack()
        q146_cmds._state["stack"] = stack
        q146_cmds._state.pop("editor", None)
        tx = EditTransaction(label="my edit")
        tx.add("test.py", "modify", "old", "new")
        stack.push(tx)

        result = _run(self.handler("preview"))
        self.assertIn("test.py", result)

    def test_undo_subcommand_case_insensitive(self):
        result = _run(self.handler("UNDO"))
        self.assertIn("Nothing to undo", result)

    def test_redo_subcommand_case_insensitive(self):
        result = _run(self.handler("REDO"))
        self.assertIn("Nothing to redo", result)

    def test_status_subcommand_case_insensitive(self):
        result = _run(self.handler("STATUS"))
        self.assertIn("Undo depth", result)

    def test_usage_lists_subcommands(self):
        result = _run(self.handler(""))
        self.assertIn("undo", result)
        self.assertIn("redo", result)
        self.assertIn("preview", result)
        self.assertIn("status", result)


if __name__ == "__main__":
    unittest.main()
