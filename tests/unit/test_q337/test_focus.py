"""Tests for lidco.productivity.focus — Focus Mode."""

from __future__ import annotations

import datetime
import unittest
from unittest import mock

from lidco.productivity.focus import (
    FocusConfig,
    FocusMode,
    FocusSession,
    FocusState,
    FocusStats,
    PomodoroPhase,
)


class TestFocusConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = FocusConfig()
        self.assertEqual(cfg.work_minutes, 25)
        self.assertEqual(cfg.short_break_minutes, 5)
        self.assertEqual(cfg.long_break_minutes, 15)
        self.assertEqual(cfg.cycles_before_long_break, 4)
        self.assertTrue(cfg.block_notifications)
        self.assertTrue(cfg.block_distractions)
        self.assertTrue(cfg.auto_break_reminders)

    def test_custom(self) -> None:
        cfg = FocusConfig(work_minutes=50, short_break_minutes=10)
        self.assertEqual(cfg.work_minutes, 50)
        self.assertEqual(cfg.short_break_minutes, 10)


class TestFocusSession(unittest.TestCase):
    def test_create(self) -> None:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        s = FocusSession(session_id="f-1", started_at=now)
        self.assertIsNone(s.ended_at)
        self.assertEqual(s.completed_cycles, 0)

    def test_with_end(self) -> None:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        s = FocusSession(session_id="f-1", started_at=now)
        end = now + datetime.timedelta(minutes=30)
        completed = s.with_end(end, completed_cycles=2, total_focus_seconds=1500.0)
        self.assertEqual(completed.ended_at, end)
        self.assertEqual(completed.completed_cycles, 2)
        self.assertEqual(completed.total_focus_seconds, 1500.0)
        self.assertIsNone(s.ended_at)  # original unchanged


class TestFocusMode(unittest.TestCase):
    def test_initial_state(self) -> None:
        fm = FocusMode()
        self.assertEqual(fm.state, FocusState.IDLE)
        self.assertIsNone(fm.current_session)
        self.assertEqual(fm.history, [])

    def test_start(self) -> None:
        fm = FocusMode()
        session = fm.start()
        self.assertEqual(fm.state, FocusState.FOCUSED)
        self.assertIsNotNone(fm.current_session)
        self.assertEqual(session.session_id, "focus-1")

    def test_start_twice_raises(self) -> None:
        fm = FocusMode()
        fm.start()
        with self.assertRaises(ValueError):
            fm.start()

    def test_stop(self) -> None:
        fm = FocusMode()
        fm.start()
        completed = fm.stop()
        self.assertIsNotNone(completed)
        self.assertIsNotNone(completed.ended_at)
        self.assertEqual(fm.state, FocusState.IDLE)
        self.assertEqual(len(fm.history), 1)

    def test_stop_no_session(self) -> None:
        fm = FocusMode()
        self.assertIsNone(fm.stop())

    def test_pause_resume(self) -> None:
        fm = FocusMode()
        fm.start()
        self.assertTrue(fm.pause())
        self.assertEqual(fm.state, FocusState.PAUSED)
        self.assertTrue(fm.resume())
        self.assertEqual(fm.state, FocusState.FOCUSED)

    def test_pause_not_focused(self) -> None:
        fm = FocusMode()
        self.assertFalse(fm.pause())

    def test_resume_not_paused(self) -> None:
        fm = FocusMode()
        self.assertFalse(fm.resume())

    def test_complete_cycle_work_to_short_break(self) -> None:
        fm = FocusMode()
        fm.start()
        phase = fm.complete_cycle()
        self.assertEqual(phase, PomodoroPhase.SHORT_BREAK)
        self.assertEqual(fm.state, FocusState.BREAK)

    def test_complete_cycle_back_to_work(self) -> None:
        fm = FocusMode()
        fm.start()
        fm.complete_cycle()  # work -> short_break
        phase = fm.complete_cycle()  # short_break -> work
        self.assertEqual(phase, PomodoroPhase.WORK)
        self.assertEqual(fm.state, FocusState.FOCUSED)

    def test_long_break_after_cycles(self) -> None:
        fm = FocusMode(FocusConfig(cycles_before_long_break=2))
        fm.start()
        fm.complete_cycle()  # work -> short_break (cycle 1)
        fm.complete_cycle()  # short_break -> work
        fm.complete_cycle()  # work -> long_break (cycle 2)
        self.assertEqual(fm.phase, PomodoroPhase.LONG_BREAK)

    def test_remaining_seconds(self) -> None:
        fm = FocusMode(FocusConfig(work_minutes=25))
        fm.start()
        remaining = fm.remaining_seconds()
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 25 * 60)

    def test_remaining_no_phase_start(self) -> None:
        fm = FocusMode()
        self.assertEqual(fm.remaining_seconds(), 0.0)

    def test_block_notification(self) -> None:
        fm = FocusMode()
        fm.start()
        self.assertTrue(fm.block_notification("slack"))
        self.assertEqual(fm.blocked_notifications, ["slack"])

    def test_block_notification_not_focused(self) -> None:
        fm = FocusMode()
        self.assertFalse(fm.block_notification("slack"))

    def test_block_notification_disabled(self) -> None:
        fm = FocusMode()
        fm.start(FocusConfig(block_notifications=False))
        self.assertFalse(fm.block_notification("slack"))

    def test_stats_empty(self) -> None:
        fm = FocusMode()
        s = fm.stats()
        self.assertEqual(s.total_sessions, 0)
        self.assertEqual(s.avg_session_minutes, 0.0)

    def test_stats_with_history(self) -> None:
        fm = FocusMode()
        fm.start()
        fm.stop()
        s = fm.stats()
        self.assertEqual(s.total_sessions, 1)

    def test_break_reminder_callback(self) -> None:
        cb = mock.Mock()
        fm = FocusMode()
        fm.set_break_reminder_callback(cb)
        fm.start()
        fm.complete_cycle()
        cb.assert_called_once()
        self.assertIn("break", cb.call_args[0][0].lower())

    def test_phase_change_callback(self) -> None:
        cb = mock.Mock()
        fm = FocusMode()
        fm.set_phase_change_callback(cb)
        fm.start()
        fm.complete_cycle()
        cb.assert_called_once_with(PomodoroPhase.SHORT_BREAK)

    def test_start_with_custom_config(self) -> None:
        fm = FocusMode()
        cfg = FocusConfig(work_minutes=50)
        session = fm.start(cfg)
        self.assertEqual(session.config.work_minutes, 50)


if __name__ == "__main__":
    unittest.main()
