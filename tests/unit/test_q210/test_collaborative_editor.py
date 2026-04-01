"""Tests for lidco.pairing.collaborative_editor."""

from __future__ import annotations

import unittest

from lidco.pairing.collaborative_editor import (
    CollaborativeEditor,
    EditOperation,
    EditorState,
)


class TestEditOperation(unittest.TestCase):
    def test_frozen(self) -> None:
        op = EditOperation(user_id="a", op_type="insert", position=0, content="x")
        with self.assertRaises(AttributeError):
            op.content = "y"  # type: ignore[misc]

    def test_defaults(self) -> None:
        op = EditOperation(user_id="a", op_type="delete", position=0)
        assert op.content == ""
        assert op.timestamp > 0


class TestEditorState(unittest.TestCase):
    def test_defaults(self) -> None:
        state = EditorState()
        assert state.content == ""
        assert state.cursors == {}
        assert state.version == 0


class TestCollaborativeEditor(unittest.TestCase):
    def setUp(self) -> None:
        self.editor = CollaborativeEditor(initial_content="hello")

    def test_initial_state(self) -> None:
        state = self.editor.get_state()
        assert state.content == "hello"
        assert state.version == 0

    def test_apply_insert(self) -> None:
        op = EditOperation(user_id="alice", op_type="insert", position=5, content=" world")
        state = self.editor.apply(op)
        assert state.content == "hello world"
        assert state.version == 1

    def test_apply_delete(self) -> None:
        op = EditOperation(user_id="bob", op_type="delete", position=0, content="hel")
        state = self.editor.apply(op)
        assert state.content == "lo"
        assert state.version == 1

    def test_apply_replace(self) -> None:
        op = EditOperation(user_id="carol", op_type="replace", position=0, content="HEL")
        state = self.editor.apply(op)
        assert state.content == "HELlo"
        assert state.version == 1

    def test_cursors(self) -> None:
        self.editor.set_cursor("alice", 3)
        assert self.editor.get_cursor("alice") == 3
        assert self.editor.get_cursor("unknown") is None

    def test_cursor_updated_on_insert(self) -> None:
        op = EditOperation(user_id="alice", op_type="insert", position=0, content="XX")
        self.editor.apply(op)
        assert self.editor.get_cursor("alice") == 2

    def test_undo(self) -> None:
        op = EditOperation(user_id="alice", op_type="insert", position=5, content="!")
        self.editor.apply(op)
        assert self.editor.get_state().content == "hello!"
        result = self.editor.undo("alice")
        assert result is not None
        assert result.content == "hello"

    def test_undo_no_ops(self) -> None:
        assert self.editor.undo("nobody") is None

    def test_participants(self) -> None:
        op1 = EditOperation(user_id="alice", op_type="insert", position=0, content="a")
        op2 = EditOperation(user_id="bob", op_type="insert", position=0, content="b")
        self.editor.apply(op1)
        self.editor.apply(op2)
        participants = self.editor.participants()
        assert "alice" in participants
        assert "bob" in participants

    def test_operation_history(self) -> None:
        op = EditOperation(user_id="alice", op_type="insert", position=0, content="x")
        self.editor.apply(op)
        history = self.editor.operation_history()
        assert len(history) == 1
        assert history[0].user_id == "alice"


if __name__ == "__main__":
    unittest.main()
