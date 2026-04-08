"""Tests for lidco.learning.progress -- ProgressDashboard, achievements, streaks."""
from __future__ import annotations

import unittest

from lidco.learning.progress import (
    Achievement,
    DailyEntry,
    ProgressDashboard,
    _next_date,
)


class TestNextDate(unittest.TestCase):
    def test_simple(self) -> None:
        self.assertEqual(_next_date("2026-04-05"), "2026-04-06")

    def test_end_of_month(self) -> None:
        self.assertEqual(_next_date("2026-04-30"), "2026-05-01")

    def test_end_of_year(self) -> None:
        self.assertEqual(_next_date("2026-12-31"), "2027-01-01")

    def test_leap_year(self) -> None:
        self.assertEqual(_next_date("2024-02-28"), "2024-02-29")
        self.assertEqual(_next_date("2024-02-29"), "2024-03-01")

    def test_non_leap_year(self) -> None:
        self.assertEqual(_next_date("2025-02-28"), "2025-03-01")


class TestAchievement(unittest.TestCase):
    def test_unlock(self) -> None:
        a = Achievement(name="first", description="First exercise")
        unlocked = a.unlock()
        self.assertFalse(a.unlocked)
        self.assertTrue(unlocked.unlocked)
        self.assertGreater(unlocked.unlocked_at, 0)

    def test_unlock_idempotent(self) -> None:
        a = Achievement(name="x", description="y", unlocked=True, unlocked_at=1.0)
        same = a.unlock()
        self.assertIs(same, a)


class TestProgressDashboard(unittest.TestCase):
    def setUp(self) -> None:
        self.dash = ProgressDashboard()

    def test_register_achievement(self) -> None:
        self.dash.register_achievement("first", "Complete first exercise")
        achs = self.dash.list_achievements()
        self.assertEqual(len(achs), 1)
        self.assertEqual(achs[0].name, "first")

    def test_register_achievement_idempotent(self) -> None:
        self.dash.register_achievement("a", "desc")
        self.dash.register_achievement("a", "desc2")
        self.assertEqual(len(self.dash.list_achievements()), 1)

    def test_unlock_achievement(self) -> None:
        self.dash.register_achievement("first", "desc")
        unlocked = self.dash.unlock_achievement("first")
        self.assertIsNotNone(unlocked)
        self.assertTrue(unlocked.unlocked)

    def test_unlock_missing(self) -> None:
        self.assertIsNone(self.dash.unlock_achievement("nonexistent"))

    def test_list_unlocked_only(self) -> None:
        self.dash.register_achievement("a", "d")
        self.dash.register_achievement("b", "d")
        self.dash.unlock_achievement("a")
        unlocked = self.dash.list_achievements(unlocked_only=True)
        self.assertEqual(len(unlocked), 1)

    def test_record_day(self) -> None:
        entry = self.dash.record_day("2026-04-01", exercises=3, xp=50)
        self.assertEqual(entry.exercises_completed, 3)
        self.assertEqual(entry.xp_earned, 50)
        self.assertEqual(self.dash.total_xp, 50)
        self.assertEqual(self.dash.exercises_completed, 3)

    def test_record_day_accumulates(self) -> None:
        self.dash.record_day("2026-04-01", exercises=2, xp=20)
        entry = self.dash.record_day("2026-04-01", exercises=1, xp=10)
        self.assertEqual(entry.exercises_completed, 3)
        self.assertEqual(entry.xp_earned, 30)

    def test_get_day(self) -> None:
        self.assertIsNone(self.dash.get_day("2026-04-01"))
        self.dash.record_day("2026-04-01", exercises=1)
        self.assertIsNotNone(self.dash.get_day("2026-04-01"))

    def test_streak_empty(self) -> None:
        self.assertEqual(self.dash.streak([]), 0)

    def test_streak_consecutive(self) -> None:
        for d in ["2026-04-01", "2026-04-02", "2026-04-03"]:
            self.dash.record_day(d, exercises=1)
        self.assertEqual(
            self.dash.streak(["2026-04-01", "2026-04-02", "2026-04-03"]),
            3,
        )

    def test_streak_with_gap(self) -> None:
        self.dash.record_day("2026-04-01", exercises=1)
        self.dash.record_day("2026-04-03", exercises=1)
        self.assertEqual(
            self.dash.streak(["2026-04-01", "2026-04-03"]),
            1,
        )

    def test_streak_untracked_dates_ignored(self) -> None:
        self.dash.record_day("2026-04-01", exercises=1)
        self.assertEqual(
            self.dash.streak(["2026-04-01", "2026-04-02"]),
            1,
        )

    def test_stats(self) -> None:
        self.dash.register_achievement("a", "d")
        self.dash.unlock_achievement("a")
        self.dash.record_day("2026-04-01", exercises=2, xp=30)
        s = self.dash.stats()
        self.assertEqual(s["total_xp"], 30)
        self.assertEqual(s["exercises_completed"], 2)
        self.assertEqual(s["days_active"], 1)
        self.assertEqual(s["achievements_unlocked"], 1)

    def test_format_summary(self) -> None:
        summary = self.dash.format_summary()
        self.assertIn("Total XP", summary)
        self.assertIn("Exercises completed", summary)


if __name__ == "__main__":
    unittest.main()
