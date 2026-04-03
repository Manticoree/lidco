"""Tests for Q274 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q274_cmds as q274_mod


def _run(coro):
    return asyncio.run(coro)


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        q274_mod._state.clear()
        from lidco.cli.commands.registry import CommandRegistry
        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q274_mod.register(reg)
        self.actions = reg._commands["actions"].handler
        self.code_action = reg._commands["code-action"].handler
        self.file_action = reg._commands["file-action"].handler
        self.git_action = reg._commands["git-action"].handler


class TestActionsCmd(_CmdTestBase):
    def test_list_empty(self):
        result = _run(self.actions("list"))
        self.assertIn("No actions", result)

    def test_find_empty(self):
        result = _run(self.actions("find editor"))
        self.assertIn("No actions", result)

    def test_execute_not_found(self):
        result = _run(self.actions("execute nope"))
        self.assertIn("not found", result)

    def test_enable_not_found(self):
        result = _run(self.actions("enable nope"))
        self.assertIn("not found", result)

    def test_disable_not_found(self):
        result = _run(self.actions("disable nope"))
        self.assertIn("not found", result)

    def test_usage(self):
        result = _run(self.actions("invalid"))
        self.assertIn("Usage", result)


class TestCodeActionCmd(_CmdTestBase):
    def test_list(self):
        result = _run(self.code_action("list"))
        self.assertIn("Extract Function", result)

    def test_list_unknown_lang(self):
        result = _run(self.code_action("list rust"))
        self.assertIn("No code actions", result)

    def test_extract(self):
        result = _run(self.code_action("extract compute"))
        self.assertIn("compute", result)

    def test_rename(self):
        result = _run(self.code_action("rename old new"))
        self.assertIn("old", result)
        self.assertIn("new", result)

    def test_wrap_try(self):
        result = _run(self.code_action("wrap-try"))
        self.assertIn("try/except", result)

    def test_comment(self):
        result = _run(self.code_action("comment"))
        self.assertIn("comment", result.lower())

    def test_usage(self):
        result = _run(self.code_action("invalid"))
        self.assertIn("Usage", result)


class TestFileActionCmd(_CmdTestBase):
    def test_create(self):
        result = _run(self.file_action("create app.py"))
        self.assertIn("Created", result)

    def test_rename(self):
        result = _run(self.file_action("rename a.py b.py"))
        self.assertIn("Renamed", result)

    def test_move(self):
        result = _run(self.file_action("move a.py lib/a.py"))
        self.assertIn("Moved", result)

    def test_delete(self):
        result = _run(self.file_action("delete tmp.py"))
        self.assertIn("Deleted", result)

    def test_history_empty(self):
        result = _run(self.file_action("history"))
        self.assertIn("No file actions", result)

    def test_undo_empty(self):
        result = _run(self.file_action("undo"))
        self.assertIn("Nothing to undo", result)

    def test_usage(self):
        result = _run(self.file_action("invalid"))
        self.assertIn("Usage", result)


class TestGitActionCmd(_CmdTestBase):
    def test_stage(self):
        result = _run(self.git_action("stage a.py b.py"))
        self.assertIn("Staged", result)

    def test_commit(self):
        result = _run(self.git_action("commit fix bug"))
        self.assertIn("Committed", result)

    def test_push(self):
        result = _run(self.git_action("push"))
        self.assertIn("Pushed", result)

    def test_branch(self):
        result = _run(self.git_action("branch feat/x"))
        self.assertIn("feat/x", result)

    def test_stash(self):
        result = _run(self.git_action("stash wip"))
        self.assertIn("Stashed", result)

    def test_stash_pop(self):
        result = _run(self.git_action("stash-pop"))
        self.assertIn("Popped", result)

    def test_history_empty(self):
        result = _run(self.git_action("history"))
        self.assertIn("No git actions", result)

    def test_usage(self):
        result = _run(self.git_action("invalid"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
