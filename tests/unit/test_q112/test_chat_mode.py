"""Tests for ChatModeManager — Task 695."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, PropertyMock

from lidco.composer.chat_mode import (
    ChatMode,
    ChatModeManager,
    ModeTransition,
)


class TestChatMode(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(ChatMode.CODE.value, "code")
        self.assertEqual(ChatMode.ASK.value, "ask")
        self.assertEqual(ChatMode.ARCHITECT.value, "architect")
        self.assertEqual(ChatMode.HELP.value, "help")


class TestModeTransition(unittest.TestCase):
    def test_creation(self):
        t = ModeTransition(
            from_mode=ChatMode.CODE,
            to_mode=ChatMode.ASK,
            timestamp="2026-01-01T00:00:00",
        )
        self.assertEqual(t.from_mode, ChatMode.CODE)
        self.assertEqual(t.to_mode, ChatMode.ASK)
        self.assertIsNone(t.warning)

    def test_creation_with_warning(self):
        t = ModeTransition(
            from_mode=ChatMode.CODE,
            to_mode=ChatMode.ASK,
            timestamp="2026-01-01",
            warning="Pending edits will be lost",
        )
        self.assertEqual(t.warning, "Pending edits will be lost")


class TestChatModeManager(unittest.TestCase):
    def test_default_mode_is_code(self):
        mgr = ChatModeManager()
        self.assertEqual(mgr.active_mode, ChatMode.CODE)

    def test_switch_to_ask(self):
        mgr = ChatModeManager()
        t = mgr.switch("ask")
        self.assertEqual(mgr.active_mode, ChatMode.ASK)
        self.assertIsInstance(t, ModeTransition)
        self.assertEqual(t.from_mode, ChatMode.CODE)
        self.assertEqual(t.to_mode, ChatMode.ASK)

    def test_switch_to_architect(self):
        mgr = ChatModeManager()
        mgr.switch("architect")
        self.assertEqual(mgr.active_mode, ChatMode.ARCHITECT)

    def test_switch_to_help(self):
        mgr = ChatModeManager()
        mgr.switch("help")
        self.assertEqual(mgr.active_mode, ChatMode.HELP)

    def test_switch_to_code(self):
        mgr = ChatModeManager()
        mgr.switch("ask")
        mgr.switch("code")
        self.assertEqual(mgr.active_mode, ChatMode.CODE)

    def test_switch_with_enum(self):
        mgr = ChatModeManager()
        mgr.switch(ChatMode.ARCHITECT)
        self.assertEqual(mgr.active_mode, ChatMode.ARCHITECT)

    def test_switch_invalid_mode_raises(self):
        mgr = ChatModeManager()
        with self.assertRaises(ValueError):
            mgr.switch("invalid_mode")

    def test_switch_records_history(self):
        mgr = ChatModeManager()
        mgr.switch("ask")
        mgr.switch("code")
        hist = mgr.history()
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[0].to_mode, ChatMode.ASK)
        self.assertEqual(hist[1].to_mode, ChatMode.CODE)

    def test_history_empty_initially(self):
        mgr = ChatModeManager()
        self.assertEqual(mgr.history(), [])

    def test_is_edit_allowed_in_code(self):
        mgr = ChatModeManager()
        self.assertTrue(mgr.is_edit_allowed())

    def test_is_edit_allowed_in_architect(self):
        mgr = ChatModeManager()
        mgr.switch("architect")
        self.assertTrue(mgr.is_edit_allowed())

    def test_is_edit_not_allowed_in_ask(self):
        mgr = ChatModeManager()
        mgr.switch("ask")
        self.assertFalse(mgr.is_edit_allowed())

    def test_is_edit_not_allowed_in_help(self):
        mgr = ChatModeManager()
        mgr.switch("help")
        self.assertFalse(mgr.is_edit_allowed())

    def test_reset(self):
        mgr = ChatModeManager()
        mgr.switch("ask")
        mgr.reset()
        self.assertEqual(mgr.active_mode, ChatMode.CODE)

    def test_switch_same_mode(self):
        mgr = ChatModeManager()
        t = mgr.switch("code")
        self.assertEqual(t.from_mode, ChatMode.CODE)
        self.assertEqual(t.to_mode, ChatMode.CODE)

    def test_switch_warning_when_pending_edits(self):
        session = MagicMock()
        session.current_plan = MagicMock()
        session._applied = False
        mgr = ChatModeManager(session=session)
        t = mgr.switch("ask")
        self.assertIsNotNone(t.warning)

    def test_switch_no_warning_without_session(self):
        mgr = ChatModeManager(session=None)
        t = mgr.switch("ask")
        self.assertIsNone(t.warning)

    def test_switch_no_warning_when_no_pending_plan(self):
        session = MagicMock()
        session.current_plan = None
        mgr = ChatModeManager(session=session)
        t = mgr.switch("ask")
        self.assertIsNone(t.warning)

    def test_transition_has_timestamp(self):
        mgr = ChatModeManager()
        t = mgr.switch("ask")
        self.assertTrue(t.timestamp)

    def test_switch_case_insensitive(self):
        mgr = ChatModeManager()
        mgr.switch("ASK")
        self.assertEqual(mgr.active_mode, ChatMode.ASK)

    def test_switch_with_leading_trailing_spaces(self):
        mgr = ChatModeManager()
        mgr.switch("  ask  ")
        self.assertEqual(mgr.active_mode, ChatMode.ASK)

    def test_multiple_transitions(self):
        mgr = ChatModeManager()
        mgr.switch("ask")
        mgr.switch("architect")
        mgr.switch("help")
        mgr.switch("code")
        hist = mgr.history()
        self.assertEqual(len(hist), 4)

    def test_reset_clears_to_code_only(self):
        mgr = ChatModeManager()
        mgr.switch("help")
        mgr.reset()
        self.assertEqual(mgr.active_mode, ChatMode.CODE)
        # history not cleared by reset, just mode
        self.assertEqual(len(mgr.history()), 1)


if __name__ == "__main__":
    unittest.main()
