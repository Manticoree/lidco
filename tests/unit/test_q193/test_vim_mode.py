"""Tests for VimMode, VimState, VimEngine."""
from __future__ import annotations

import unittest

from lidco.input.vim_mode import VimAction, VimEngine, VimMode, VimState


class TestVimModeEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(VimMode.NORMAL.value, "normal")
        self.assertEqual(VimMode.INSERT.value, "insert")
        self.assertEqual(VimMode.VISUAL.value, "visual")
        self.assertEqual(VimMode.COMMAND.value, "command")

    def test_all_members(self):
        self.assertEqual(len(VimMode), 4)


class TestVimState(unittest.TestCase):
    def test_frozen(self):
        s = VimState(mode=VimMode.NORMAL, cursor_pos=0, register="", count=0)
        with self.assertRaises(AttributeError):
            s.mode = VimMode.INSERT  # type: ignore[misc]

    def test_fields(self):
        s = VimState(mode=VimMode.INSERT, cursor_pos=5, register="abc", count=3)
        self.assertEqual(s.mode, VimMode.INSERT)
        self.assertEqual(s.cursor_pos, 5)
        self.assertEqual(s.register, "abc")
        self.assertEqual(s.count, 3)


class TestVimAction(unittest.TestCase):
    def test_frozen(self):
        a = VimAction(action_type="MOVE", params={"delta": 1})
        with self.assertRaises(AttributeError):
            a.action_type = "DELETE"  # type: ignore[misc]

    def test_fields(self):
        a = VimAction(action_type="YANK", params={"count": 2})
        self.assertEqual(a.action_type, "YANK")
        self.assertEqual(a.params["count"], 2)


class TestVimEngineInit(unittest.TestCase):
    def test_default_mode(self):
        e = VimEngine()
        self.assertEqual(e.mode, VimMode.NORMAL)

    def test_custom_initial_mode(self):
        e = VimEngine(initial_mode=VimMode.INSERT)
        self.assertEqual(e.mode, VimMode.INSERT)

    def test_initial_state(self):
        e = VimEngine()
        s = e.state
        self.assertEqual(s.cursor_pos, 0)
        self.assertEqual(s.register, "")
        self.assertEqual(s.count, 0)


class TestVimEngineSwitchMode(unittest.TestCase):
    def test_switch_returns_new_instance(self):
        e = VimEngine()
        e2 = e.switch_mode(VimMode.INSERT)
        self.assertIsNot(e, e2)
        self.assertEqual(e.mode, VimMode.NORMAL)
        self.assertEqual(e2.mode, VimMode.INSERT)

    def test_switch_preserves_cursor(self):
        e = VimEngine()
        e.process_key("l")
        e2 = e.switch_mode(VimMode.VISUAL)
        self.assertEqual(e2.state.cursor_pos, 1)


class TestVimEngineNormalMode(unittest.TestCase):
    def test_movement_h(self):
        e = VimEngine()
        e.process_key("l")  # move right
        a = e.process_key("h")
        self.assertEqual(a.action_type, "MOVE")
        self.assertEqual(e.state.cursor_pos, 0)

    def test_movement_l(self):
        e = VimEngine()
        a = e.process_key("l")
        self.assertEqual(a.action_type, "MOVE")
        self.assertEqual(e.state.cursor_pos, 1)

    def test_switch_to_insert(self):
        e = VimEngine()
        a = e.process_key("i")
        self.assertEqual(a.action_type, "CHANGE_MODE")
        self.assertEqual(e.mode, VimMode.INSERT)

    def test_switch_to_visual(self):
        e = VimEngine()
        e.process_key("v")
        self.assertEqual(e.mode, VimMode.VISUAL)

    def test_switch_to_command(self):
        e = VimEngine()
        e.process_key(":")
        self.assertEqual(e.mode, VimMode.COMMAND)

    def test_delete_x(self):
        e = VimEngine()
        a = e.process_key("x")
        self.assertEqual(a.action_type, "DELETE")

    def test_paste_p(self):
        e = VimEngine()
        a = e.process_key("p")
        self.assertEqual(a.action_type, "PASTE")

    def test_search_slash(self):
        e = VimEngine()
        a = e.process_key("/")
        self.assertEqual(a.action_type, "SEARCH")

    def test_count_prefix(self):
        e = VimEngine()
        e.process_key("3")
        a = e.process_key("l")
        self.assertEqual(a.action_type, "MOVE")
        self.assertEqual(a.params["delta"], 3)
        self.assertEqual(e.state.cursor_pos, 3)


class TestVimEngineInsertMode(unittest.TestCase):
    def test_escape_returns_to_normal(self):
        e = VimEngine(initial_mode=VimMode.INSERT)
        a = e.process_key("Escape")
        self.assertEqual(a.action_type, "CHANGE_MODE")
        self.assertEqual(e.mode, VimMode.NORMAL)

    def test_char_insert(self):
        e = VimEngine(initial_mode=VimMode.INSERT)
        a = e.process_key("a")
        self.assertEqual(a.action_type, "COMMAND")
        self.assertEqual(a.params["char"], "a")


class TestVimEngineVisualMode(unittest.TestCase):
    def test_escape_returns_to_normal(self):
        e = VimEngine(initial_mode=VimMode.VISUAL)
        e.process_key("Escape")
        self.assertEqual(e.mode, VimMode.NORMAL)

    def test_yank_returns_to_normal(self):
        e = VimEngine(initial_mode=VimMode.VISUAL)
        a = e.process_key("y")
        self.assertEqual(a.action_type, "YANK")
        self.assertEqual(e.mode, VimMode.NORMAL)


if __name__ == "__main__":
    unittest.main()
