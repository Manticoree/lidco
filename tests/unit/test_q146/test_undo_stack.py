"""Tests for UndoStack (Q146 task 863)."""
from __future__ import annotations

import unittest

from lidco.editing.edit_transaction import EditTransaction
from lidco.editing.undo_stack import StackState, UndoStack


def _tx(label: str = "test") -> EditTransaction:
    tx = EditTransaction(label=label)
    tx.add("f.py", "modify", "old", "new")
    return tx


class TestStackState(unittest.TestCase):
    def test_fields(self):
        st = StackState(undo_depth=3, redo_depth=1, current_label="edit")
        self.assertEqual(st.undo_depth, 3)
        self.assertEqual(st.redo_depth, 1)
        self.assertEqual(st.current_label, "edit")


class TestUndoStack(unittest.TestCase):
    def test_empty_stack(self):
        s = UndoStack()
        self.assertFalse(s.can_undo)
        self.assertFalse(s.can_redo)

    def test_push_enables_undo(self):
        s = UndoStack()
        s.push(_tx("a"))
        self.assertTrue(s.can_undo)
        self.assertFalse(s.can_redo)

    def test_undo_returns_transaction(self):
        s = UndoStack()
        s.push(_tx("a"))
        tx = s.undo()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.label, "a")

    def test_undo_moves_to_redo(self):
        s = UndoStack()
        s.push(_tx("a"))
        s.undo()
        self.assertFalse(s.can_undo)
        self.assertTrue(s.can_redo)

    def test_redo_returns_transaction(self):
        s = UndoStack()
        s.push(_tx("a"))
        s.undo()
        tx = s.redo()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.label, "a")

    def test_redo_moves_to_undo(self):
        s = UndoStack()
        s.push(_tx("a"))
        s.undo()
        s.redo()
        self.assertTrue(s.can_undo)
        self.assertFalse(s.can_redo)

    def test_undo_empty_returns_none(self):
        s = UndoStack()
        self.assertIsNone(s.undo())

    def test_redo_empty_returns_none(self):
        s = UndoStack()
        self.assertIsNone(s.redo())

    def test_push_clears_redo(self):
        s = UndoStack()
        s.push(_tx("a"))
        s.undo()
        self.assertTrue(s.can_redo)
        s.push(_tx("b"))
        self.assertFalse(s.can_redo)

    def test_max_depth(self):
        s = UndoStack(max_depth=3)
        for i in range(5):
            s.push(_tx(f"t{i}"))
        st = s.state()
        self.assertEqual(st.undo_depth, 3)

    def test_max_depth_oldest_discarded(self):
        s = UndoStack(max_depth=2)
        s.push(_tx("first"))
        s.push(_tx("second"))
        s.push(_tx("third"))
        tx = s.undo()
        self.assertEqual(tx.label, "third")
        tx = s.undo()
        self.assertEqual(tx.label, "second")
        self.assertIsNone(s.undo())

    def test_peek_undo(self):
        s = UndoStack()
        s.push(_tx("a"))
        peek = s.peek_undo()
        self.assertEqual(peek.label, "a")
        # peek should not pop
        self.assertTrue(s.can_undo)

    def test_peek_undo_empty(self):
        s = UndoStack()
        self.assertIsNone(s.peek_undo())

    def test_state_empty(self):
        s = UndoStack()
        st = s.state()
        self.assertEqual(st.undo_depth, 0)
        self.assertEqual(st.redo_depth, 0)
        self.assertIsNone(st.current_label)

    def test_state_with_items(self):
        s = UndoStack()
        s.push(_tx("x"))
        s.push(_tx("y"))
        st = s.state()
        self.assertEqual(st.undo_depth, 2)
        self.assertEqual(st.redo_depth, 0)
        self.assertEqual(st.current_label, "y")

    def test_state_after_undo(self):
        s = UndoStack()
        s.push(_tx("a"))
        s.push(_tx("b"))
        s.undo()
        st = s.state()
        self.assertEqual(st.undo_depth, 1)
        self.assertEqual(st.redo_depth, 1)
        self.assertEqual(st.current_label, "a")

    def test_clear(self):
        s = UndoStack()
        s.push(_tx("a"))
        s.push(_tx("b"))
        s.undo()
        s.clear()
        self.assertFalse(s.can_undo)
        self.assertFalse(s.can_redo)

    def test_multiple_undo_redo(self):
        s = UndoStack()
        s.push(_tx("a"))
        s.push(_tx("b"))
        s.push(_tx("c"))
        self.assertEqual(s.undo().label, "c")
        self.assertEqual(s.undo().label, "b")
        self.assertEqual(s.redo().label, "b")
        self.assertEqual(s.redo().label, "c")

    def test_default_max_depth(self):
        s = UndoStack()
        self.assertEqual(s.max_depth, 50)

    def test_push_single_then_state(self):
        s = UndoStack()
        s.push(_tx("only"))
        st = s.state()
        self.assertEqual(st.current_label, "only")


if __name__ == "__main__":
    unittest.main()
