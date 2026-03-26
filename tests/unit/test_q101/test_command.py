"""Tests for src/lidco/patterns/command.py — Command, SetValueCommand, DeleteKeyCommand, CommandHistory."""
import pytest
from lidco.patterns.command import (
    Command, SetValueCommand, DeleteKeyCommand, CommandHistory,
)


class TestSetValueCommand:
    def test_execute_sets_value(self):
        target = {}
        cmd = SetValueCommand(target=target, key="k", value="v")
        cmd.execute()
        assert target["k"] == "v"

    def test_execute_returns_old_value(self):
        target = {"k": "old"}
        cmd = SetValueCommand(target=target, key="k", value="new")
        result = cmd.execute()
        assert result == "old"

    def test_execute_returns_none_for_new_key(self):
        target = {}
        cmd = SetValueCommand(target=target, key="k", value="v")
        result = cmd.execute()
        assert result is None

    def test_undo_restores_old_value(self):
        target = {"k": "old"}
        cmd = SetValueCommand(target=target, key="k", value="new")
        cmd.execute()
        cmd.undo()
        assert target["k"] == "old"

    def test_undo_removes_new_key(self):
        target = {}
        cmd = SetValueCommand(target=target, key="k", value="v")
        cmd.execute()
        cmd.undo()
        assert "k" not in target

    def test_description_default(self):
        cmd = SetValueCommand(target={}, key="k", value="v")
        assert isinstance(cmd.description, str)


class TestDeleteKeyCommand:
    def test_execute_deletes_key(self):
        target = {"k": "v"}
        cmd = DeleteKeyCommand(target=target, key="k")
        cmd.execute()
        assert "k" not in target

    def test_execute_returns_deleted_value(self):
        target = {"k": "v"}
        cmd = DeleteKeyCommand(target=target, key="k")
        result = cmd.execute()
        assert result == "v"

    def test_execute_missing_key_returns_none(self):
        target = {}
        cmd = DeleteKeyCommand(target=target, key="k")
        result = cmd.execute()
        assert result is None

    def test_undo_restores_deleted_key(self):
        target = {"k": "v"}
        cmd = DeleteKeyCommand(target=target, key="k")
        cmd.execute()
        cmd.undo()
        assert target["k"] == "v"

    def test_undo_noop_when_key_was_missing(self):
        target = {}
        cmd = DeleteKeyCommand(target=target, key="k")
        cmd.execute()
        cmd.undo()
        assert "k" not in target


class TestCommandHistory:
    def test_execute_and_undo(self):
        target = {}
        history = CommandHistory()
        cmd = SetValueCommand(target=target, key="x", value=10)
        history.execute(cmd)
        assert target["x"] == 10
        history.undo()
        assert "x" not in target

    def test_undo_empty_returns_none(self):
        history = CommandHistory()
        assert history.undo() is None

    def test_redo_after_undo(self):
        target = {}
        history = CommandHistory()
        cmd = SetValueCommand(target=target, key="x", value=1)
        history.execute(cmd)
        history.undo()
        history.redo()
        assert target["x"] == 1

    def test_redo_empty_returns_none(self):
        history = CommandHistory()
        assert history.redo() is None

    def test_new_command_clears_redo(self):
        target = {}
        history = CommandHistory()
        c1 = SetValueCommand(target=target, key="a", value=1)
        c2 = SetValueCommand(target=target, key="b", value=2)
        c3 = SetValueCommand(target=target, key="c", value=3)
        history.execute(c1)
        history.execute(c2)
        history.undo()
        assert history.can_redo
        history.execute(c3)
        assert not history.can_redo

    def test_max_history(self):
        target = {}
        history = CommandHistory(max_history=2)
        for i in range(5):
            history.execute(SetValueCommand(target=target, key=f"k{i}", value=i))
        assert len(history.history) == 2

    def test_can_undo_can_redo(self):
        target = {}
        history = CommandHistory()
        assert not history.can_undo
        assert not history.can_redo
        history.execute(SetValueCommand(target=target, key="a", value=1))
        assert history.can_undo
        history.undo()
        assert history.can_redo

    def test_clear(self):
        target = {}
        history = CommandHistory()
        history.execute(SetValueCommand(target=target, key="a", value=1))
        history.clear()
        assert not history.can_undo
        assert not history.can_redo

    def test_history_oldest_first(self):
        target = {}
        history = CommandHistory()
        c1 = SetValueCommand(target=target, key="a", value=1, description="first")
        c2 = SetValueCommand(target=target, key="b", value=2, description="second")
        history.execute(c1)
        history.execute(c2)
        h = history.history
        assert h[0].description == "first"
        assert h[1].description == "second"

    def test_command_protocol(self):
        """SetValueCommand satisfies the Command protocol."""
        cmd = SetValueCommand(target={}, key="k", value="v")
        assert isinstance(cmd, Command)
