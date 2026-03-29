"""Tests for LiveTodoTracker — Task 692."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from lidco.tasks.live_todo import (
    LiveTodoTracker,
    TodoBoardState,
    TodoItem,
    TodoStatus,
)


class TestTodoStatus(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(TodoStatus.PENDING.value, "pending")
        self.assertEqual(TodoStatus.ACTIVE.value, "active")
        self.assertEqual(TodoStatus.DONE.value, "done")
        self.assertEqual(TodoStatus.BLOCKED.value, "blocked")


class TestTodoItem(unittest.TestCase):
    def test_defaults(self):
        item = TodoItem(id="t1", label="Do stuff")
        self.assertEqual(item.status, TodoStatus.PENDING)
        self.assertIsNone(item.blocked_reason)
        self.assertEqual(item.depends_on, [])

    def test_custom_fields(self):
        item = TodoItem(
            id="t2",
            label="Build",
            status=TodoStatus.ACTIVE,
            blocked_reason=None,
            depends_on=["t1"],
        )
        self.assertEqual(item.depends_on, ["t1"])
        self.assertEqual(item.status, TodoStatus.ACTIVE)


class TestTodoBoardState(unittest.TestCase):
    def _make_board(self):
        items = [
            TodoItem(id="1", label="A", status=TodoStatus.PENDING),
            TodoItem(id="2", label="B", status=TodoStatus.ACTIVE),
            TodoItem(id="3", label="C", status=TodoStatus.DONE),
            TodoItem(id="4", label="D", status=TodoStatus.BLOCKED, blocked_reason="dep"),
        ]
        return TodoBoardState(items=items)

    def test_pending_filter(self):
        board = self._make_board()
        self.assertEqual(len(board.pending), 1)
        self.assertEqual(board.pending[0].id, "1")

    def test_active_filter(self):
        board = self._make_board()
        self.assertEqual(len(board.active), 1)
        self.assertEqual(board.active[0].id, "2")

    def test_done_filter(self):
        board = self._make_board()
        self.assertEqual(len(board.done), 1)
        self.assertEqual(board.done[0].id, "3")

    def test_blocked_filter(self):
        board = self._make_board()
        self.assertEqual(len(board.blocked), 1)
        self.assertEqual(board.blocked[0].id, "4")

    def test_empty_board(self):
        board = TodoBoardState(items=[])
        self.assertEqual(board.pending, [])
        self.assertEqual(board.active, [])
        self.assertEqual(board.done, [])
        self.assertEqual(board.blocked, [])


class TestLiveTodoTracker(unittest.TestCase):
    def test_add_item(self):
        tracker = LiveTodoTracker()
        item = TodoItem(id="1", label="Task 1")
        tracker.add_item(item)
        state = tracker.get_state()
        self.assertEqual(len(state.items), 1)

    def test_add_multiple_items(self):
        tracker = LiveTodoTracker()
        tracker.add_item(TodoItem(id="1", label="A"))
        tracker.add_item(TodoItem(id="2", label="B"))
        self.assertEqual(len(tracker.get_state().items), 2)

    def test_update_status(self):
        tracker = LiveTodoTracker()
        tracker.add_item(TodoItem(id="1", label="A"))
        tracker.update("1", TodoStatus.DONE)
        state = tracker.get_state()
        self.assertEqual(state.items[0].status, TodoStatus.DONE)

    def test_update_blocked_with_reason(self):
        tracker = LiveTodoTracker()
        tracker.add_item(TodoItem(id="1", label="A"))
        tracker.update("1", TodoStatus.BLOCKED, blocked_reason="waiting for API")
        state = tracker.get_state()
        self.assertEqual(state.items[0].blocked_reason, "waiting for API")

    def test_update_nonexistent_item_raises(self):
        tracker = LiveTodoTracker()
        with self.assertRaises(KeyError):
            tracker.update("missing", TodoStatus.DONE)

    def test_render_ascii_pending(self):
        tracker = LiveTodoTracker()
        tracker.add_item(TodoItem(id="1", label="Do X"))
        output = tracker.render_ascii()
        self.assertIn("[ ]", output)
        self.assertIn("Do X", output)
        self.assertIn("pending", output)

    def test_render_ascii_active(self):
        tracker = LiveTodoTracker()
        tracker.add_item(TodoItem(id="1", label="Do X", status=TodoStatus.ACTIVE))
        output = tracker.render_ascii()
        self.assertIn("[>]", output)
        self.assertIn("active", output)

    def test_render_ascii_done(self):
        tracker = LiveTodoTracker()
        tracker.add_item(TodoItem(id="1", label="Do X", status=TodoStatus.DONE))
        output = tracker.render_ascii()
        self.assertIn("[x]", output)
        self.assertIn("done", output)

    def test_render_ascii_blocked(self):
        tracker = LiveTodoTracker()
        tracker.add_item(
            TodoItem(id="1", label="Do X", status=TodoStatus.BLOCKED, blocked_reason="reason")
        )
        output = tracker.render_ascii()
        self.assertIn("[!]", output)
        self.assertIn("blocked", output)
        self.assertIn("reason", output)

    def test_render_ascii_empty(self):
        tracker = LiveTodoTracker()
        output = tracker.render_ascii()
        self.assertEqual(output, "")

    def test_clear(self):
        tracker = LiveTodoTracker()
        tracker.add_item(TodoItem(id="1", label="A"))
        tracker.clear()
        self.assertEqual(len(tracker.get_state().items), 0)

    def test_from_plan(self):
        tracker = LiveTodoTracker()
        plan_items = [
            {"id": "s1", "label": "Step 1", "depends_on": []},
            {"id": "s2", "label": "Step 2", "depends_on": ["s1"]},
        ]
        tracker.from_plan(plan_items)
        state = tracker.get_state()
        self.assertEqual(len(state.items), 2)
        self.assertEqual(state.items[1].depends_on, ["s1"])

    def test_from_plan_clears_existing(self):
        tracker = LiveTodoTracker()
        tracker.add_item(TodoItem(id="old", label="Old"))
        tracker.from_plan([{"id": "new", "label": "New"}])
        state = tracker.get_state()
        self.assertEqual(len(state.items), 1)
        self.assertEqual(state.items[0].id, "new")

    def test_event_bus_fires_on_update(self):
        bus = MagicMock()
        tracker = LiveTodoTracker(event_bus=bus)
        tracker.add_item(TodoItem(id="1", label="A"))
        tracker.update("1", TodoStatus.DONE)
        bus.publish.assert_called_once()
        call_args = bus.publish.call_args
        self.assertEqual(call_args[0][0], "todo.updated")

    def test_event_bus_not_required(self):
        tracker = LiveTodoTracker(event_bus=None)
        tracker.add_item(TodoItem(id="1", label="A"))
        tracker.update("1", TodoStatus.ACTIVE)
        # no error

    def test_get_state_returns_copy(self):
        tracker = LiveTodoTracker()
        tracker.add_item(TodoItem(id="1", label="A"))
        state1 = tracker.get_state()
        tracker.add_item(TodoItem(id="2", label="B"))
        state2 = tracker.get_state()
        self.assertEqual(len(state1.items), 1)
        self.assertEqual(len(state2.items), 2)

    def test_from_plan_missing_depends_on(self):
        tracker = LiveTodoTracker()
        tracker.from_plan([{"id": "x", "label": "No deps"}])
        state = tracker.get_state()
        self.assertEqual(state.items[0].depends_on, [])


if __name__ == "__main__":
    unittest.main()
