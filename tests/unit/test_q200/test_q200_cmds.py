"""Tests for lidco.cli.commands.q200_cmds — task management CLI commands."""
from __future__ import annotations

import asyncio

from lidco.cli.commands.registry import CommandRegistry, SlashCommand
from lidco.cli.commands import q200_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ200Commands:
    def setup_method(self):
        q200_cmds._state.clear()
        self.registry = CommandRegistry()
        q200_cmds.register(self.registry)

    def test_task_create(self):
        handler = self.registry._commands["task-create"].handler
        result = _run(handler("build Build the project"))
        assert "Created task" in result
        assert "build" in result

    def test_task_create_no_args(self):
        handler = self.registry._commands["task-create"].handler
        result = _run(handler(""))
        assert "Usage" in result

    def test_task_list_empty(self):
        handler = self.registry._commands["task-list"].handler
        result = _run(handler(""))
        assert "No tasks found" in result

    def test_task_list_with_tasks(self):
        create = self.registry._commands["task-create"].handler
        _run(create("alpha"))
        _run(create("beta"))
        handler = self.registry._commands["task-list"].handler
        result = _run(handler(""))
        assert "2 task(s)" in result

    def test_task_status(self):
        create = self.registry._commands["task-create"].handler
        out = _run(create("mytest"))
        task_id = out.split()[2].rstrip(":")
        handler = self.registry._commands["task-status"].handler
        result = _run(handler(task_id))
        assert "mytest" in result
        assert "pending" in result

    def test_task_status_not_found(self):
        handler = self.registry._commands["task-status"].handler
        result = _run(handler("badid"))
        assert "not found" in result

    def test_task_output_no_output(self):
        create = self.registry._commands["task-create"].handler
        out = _run(create("x"))
        task_id = out.split()[2].rstrip(":")
        handler = self.registry._commands["task-output"].handler
        result = _run(handler(task_id))
        assert "No output" in result
