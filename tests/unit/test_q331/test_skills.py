"""Tests for lidco.learning.skills -- SkillTracker, SkillEntry."""
from __future__ import annotations

import unittest

from lidco.learning.skills import SkillEntry, SkillSnapshot, SkillTracker


class TestSkillEntry(unittest.TestCase):
    def test_initial_state(self) -> None:
        e = SkillEntry(name="python", category="language")
        self.assertEqual(e.proficiency, 0.0)
        self.assertEqual(e.xp, 0)
        self.assertEqual(e.level(), "beginner")

    def test_record_increases_xp(self) -> None:
        e = SkillEntry(name="python", category="language")
        e.record(100, "wrote scripts")
        self.assertEqual(e.xp, 100)
        self.assertAlmostEqual(e.proficiency, 0.1)
        self.assertEqual(len(e.history), 1)
        self.assertEqual(e.history[0]["note"], "wrote scripts")

    def test_record_negative_ignored(self) -> None:
        e = SkillEntry(name="go", category="language")
        e.record(-50)
        self.assertEqual(e.xp, 0)

    def test_proficiency_capped_at_1(self) -> None:
        e = SkillEntry(name="rust", category="language")
        e.record(5000)
        self.assertEqual(e.proficiency, 1.0)

    def test_level_thresholds(self) -> None:
        e = SkillEntry(name="ts", category="language")
        self.assertEqual(e.level(), "beginner")
        e.record(200)
        self.assertEqual(e.level(), "intermediate")
        e.record(300)
        self.assertEqual(e.level(), "advanced")
        e.record(500)
        self.assertEqual(e.level(), "expert")


class TestSkillTracker(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = SkillTracker()

    def test_add_skill(self) -> None:
        e = self.tracker.add_skill("python", "language")
        self.assertEqual(e.name, "python")
        self.assertEqual(e.category, "language")

    def test_add_skill_idempotent(self) -> None:
        e1 = self.tracker.add_skill("python")
        e2 = self.tracker.add_skill("python")
        self.assertIs(e1, e2)

    def test_record_usage_creates_skill(self) -> None:
        e = self.tracker.record_usage("java", 50)
        self.assertEqual(e.name, "java")
        self.assertEqual(e.xp, 50)

    def test_record_usage_existing(self) -> None:
        self.tracker.add_skill("go", "language")
        e = self.tracker.record_usage("go", 20)
        self.assertEqual(e.xp, 20)

    def test_get_skill(self) -> None:
        self.tracker.add_skill("python")
        self.assertIsNotNone(self.tracker.get_skill("python"))
        self.assertIsNone(self.tracker.get_skill("nonexistent"))

    def test_list_skills_sorted(self) -> None:
        self.tracker.record_usage("python", 500)
        self.tracker.record_usage("go", 100)
        skills = self.tracker.list_skills()
        self.assertEqual(skills[0].name, "python")

    def test_list_skills_by_category(self) -> None:
        self.tracker.add_skill("python", "language")
        self.tracker.add_skill("react", "framework")
        langs = self.tracker.list_skills("language")
        self.assertEqual(len(langs), 1)
        self.assertEqual(langs[0].name, "python")

    def test_snapshot(self) -> None:
        self.tracker.record_usage("python", 100)
        snap = self.tracker.snapshot()
        self.assertIsInstance(snap, SkillSnapshot)
        self.assertIn("python", snap.skills)
        self.assertEqual(len(self.tracker.snapshots), 1)

    def test_growth(self) -> None:
        self.tracker.record_usage("python", 100)
        self.tracker.snapshot()
        self.tracker.record_usage("python", 200)
        self.tracker.snapshot()
        growth = self.tracker.growth("python")
        self.assertEqual(len(growth), 2)
        self.assertGreater(growth[1]["proficiency"], growth[0]["proficiency"])

    def test_growth_missing_skill(self) -> None:
        self.assertEqual(self.tracker.growth("nonexistent"), [])

    def test_top_skills(self) -> None:
        for i, lang in enumerate(["a", "b", "c", "d", "e", "f"]):
            self.tracker.record_usage(lang, (i + 1) * 100)
        top3 = self.tracker.top_skills(3)
        self.assertEqual(len(top3), 3)
        self.assertEqual(top3[0].name, "f")

    def test_weak_skills(self) -> None:
        self.tracker.record_usage("strong", 800)
        self.tracker.record_usage("weak", 10)
        weak = self.tracker.weak_skills(0.3)
        self.assertEqual(len(weak), 1)
        self.assertEqual(weak[0].name, "weak")

    def test_format_summary_empty(self) -> None:
        self.assertIn("No skills", self.tracker.format_summary())

    def test_format_summary_with_skills(self) -> None:
        self.tracker.record_usage("python", 500)
        summary = self.tracker.format_summary()
        self.assertIn("python", summary)
        self.assertIn("Skills (1)", summary)


if __name__ == "__main__":
    unittest.main()
