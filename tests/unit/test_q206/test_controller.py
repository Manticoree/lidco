"""Tests for computer_use.controller."""
from __future__ import annotations

import unittest

from lidco.computer_use.controller import Coordinate, ScreenController


class TestScreenControllerMove(unittest.TestCase):
    def setUp(self):
        self.ctrl = ScreenController(width=800, height=600)

    def test_move_returns_coordinate(self):
        pos = self.ctrl.move(100, 200)
        self.assertEqual(pos, Coordinate(100, 200))

    def test_move_clamps_to_bounds(self):
        pos = self.ctrl.move(9999, -5)
        self.assertEqual(pos, Coordinate(799, 0))

    def test_cursor_position_after_move(self):
        self.ctrl.move(50, 60)
        self.assertEqual(self.ctrl.cursor_position(), Coordinate(50, 60))


class TestScreenControllerClick(unittest.TestCase):
    def setUp(self):
        self.ctrl = ScreenController()

    def test_click_returns_coordinate(self):
        pos = self.ctrl.click(10, 20)
        self.assertEqual(pos, Coordinate(10, 20))

    def test_click_with_button(self):
        self.ctrl.click(10, 20, button="right")
        hist = self.ctrl.action_history()
        click_actions = [h for h in hist if h["action"] == "click"]
        self.assertEqual(click_actions[-1]["button"], "right")

    def test_double_click(self):
        pos = self.ctrl.double_click(30, 40)
        self.assertEqual(pos, Coordinate(30, 40))
        hist = self.ctrl.action_history()
        self.assertTrue(any(h["action"] == "double_click" for h in hist))


class TestScreenControllerDrag(unittest.TestCase):
    def test_drag_returns_start_end(self):
        ctrl = ScreenController()
        start, end = ctrl.drag(10, 20, 100, 200)
        self.assertEqual(start, Coordinate(10, 20))
        self.assertEqual(end, Coordinate(100, 200))
        self.assertEqual(ctrl.cursor_position(), Coordinate(100, 200))


class TestScreenControllerTypeAndHotkey(unittest.TestCase):
    def setUp(self):
        self.ctrl = ScreenController()

    def test_type_text(self):
        result = self.ctrl.type_text("hello world")
        self.assertEqual(result, "hello world")

    def test_hotkey(self):
        result = self.ctrl.hotkey("ctrl", "shift", "p")
        self.assertEqual(result, "ctrl+shift+p")


class TestScreenControllerHistory(unittest.TestCase):
    def test_history_records_actions(self):
        ctrl = ScreenController()
        ctrl.move(1, 2)
        ctrl.click(3, 4)
        hist = ctrl.action_history()
        self.assertGreaterEqual(len(hist), 2)

    def test_clear_history(self):
        ctrl = ScreenController()
        ctrl.move(1, 2)
        ctrl.clear_history()
        self.assertEqual(len(ctrl.action_history()), 0)

    def test_screen_size(self):
        ctrl = ScreenController(1024, 768)
        self.assertEqual(ctrl.screen_size(), (1024, 768))


if __name__ == "__main__":
    unittest.main()
