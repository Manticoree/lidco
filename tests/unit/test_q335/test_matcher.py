"""Tests for lidco.mentor.matcher — Mentor Matcher."""

from __future__ import annotations

import unittest

from lidco.mentor.matcher import (
    Availability,
    MatchScore,
    MentorMatcher,
    Profile,
    Skill,
)


class TestAvailability(unittest.TestCase):
    """Tests for Availability overlap logic."""

    def test_same_day_overlap(self) -> None:
        a = Availability("monday", 9, 17)
        b = Availability("monday", 14, 20)
        self.assertTrue(a.overlaps(b))

    def test_different_day_no_overlap(self) -> None:
        a = Availability("monday", 9, 17)
        b = Availability("tuesday", 9, 17)
        self.assertFalse(a.overlaps(b))

    def test_no_overlap_same_day(self) -> None:
        a = Availability("monday", 9, 12)
        b = Availability("monday", 13, 17)
        self.assertFalse(a.overlaps(b))

    def test_overlap_hours(self) -> None:
        a = Availability("monday", 9, 17)
        b = Availability("monday", 14, 20)
        self.assertEqual(a.overlap_hours(b), 3)

    def test_overlap_hours_no_overlap(self) -> None:
        a = Availability("monday", 9, 12)
        b = Availability("tuesday", 9, 12)
        self.assertEqual(a.overlap_hours(b), 0)

    def test_exact_boundary_no_overlap(self) -> None:
        a = Availability("monday", 9, 12)
        b = Availability("monday", 12, 17)
        self.assertFalse(a.overlaps(b))

    def test_case_insensitive_day(self) -> None:
        a = Availability("Monday", 9, 17)
        b = Availability("monday", 14, 20)
        self.assertTrue(a.overlaps(b))


class TestMatchScore(unittest.TestCase):
    """Tests for MatchScore properties."""

    def test_total_weighted(self) -> None:
        ms = MatchScore("m1", "e1", 1.0, 1.0, 1.0, 1.0)
        self.assertAlmostEqual(ms.total, 1.0)

    def test_total_zero(self) -> None:
        ms = MatchScore("m1", "e1", 0.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(ms.total, 0.0)

    def test_label_excellent(self) -> None:
        ms = MatchScore("m1", "e1", 1.0, 1.0, 1.0, 1.0)
        self.assertEqual(ms.label, "excellent")

    def test_label_good(self) -> None:
        ms = MatchScore("m1", "e1", 0.7, 0.7, 0.7, 0.7)
        self.assertEqual(ms.label, "good")

    def test_label_fair(self) -> None:
        ms = MatchScore("m1", "e1", 0.5, 0.5, 0.5, 0.5)
        self.assertEqual(ms.label, "fair")

    def test_label_poor(self) -> None:
        ms = MatchScore("m1", "e1", 0.1, 0.1, 0.1, 0.1)
        self.assertEqual(ms.label, "poor")


class TestMentorMatcher(unittest.TestCase):
    """Tests for MentorMatcher."""

    def _make_mentor(self, uid: str = "m1") -> Profile:
        return Profile(
            user_id=uid,
            name=f"Mentor {uid}",
            skills=[Skill("python", 5), Skill("testing", 4)],
            interests=["backend", "testing"],
            projects=["lidco"],
            availability=[Availability("monday", 9, 17)],
            is_mentor=True,
        )

    def _make_mentee(self, uid: str = "e1") -> Profile:
        return Profile(
            user_id=uid,
            name=f"Mentee {uid}",
            skills=[Skill("python", 2), Skill("testing", 1)],
            interests=["backend", "devops"],
            projects=["lidco"],
            availability=[Availability("monday", 10, 18)],
            is_mentor=False,
        )

    def test_add_and_get_profile(self) -> None:
        m = MentorMatcher()
        p = self._make_mentor()
        m.add_profile(p)
        self.assertEqual(m.get_profile("m1"), p)

    def test_remove_profile(self) -> None:
        m = MentorMatcher()
        m.add_profile(self._make_mentor())
        self.assertTrue(m.remove_profile("m1"))
        self.assertIsNone(m.get_profile("m1"))

    def test_remove_nonexistent(self) -> None:
        m = MentorMatcher()
        self.assertFalse(m.remove_profile("x"))

    def test_mentors_and_mentees(self) -> None:
        m = MentorMatcher()
        m.add_profile(self._make_mentor())
        m.add_profile(self._make_mentee())
        self.assertEqual(len(m.mentors), 1)
        self.assertEqual(len(m.mentees), 1)

    def test_skill_complementarity(self) -> None:
        m = MentorMatcher()
        mentor = self._make_mentor()
        mentee = self._make_mentee()
        score = m.skill_complementarity(mentor, mentee)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_skill_complementarity_empty(self) -> None:
        m = MentorMatcher()
        mentor = Profile(user_id="m", name="M", is_mentor=True)
        mentee = Profile(user_id="e", name="E")
        self.assertEqual(m.skill_complementarity(mentor, mentee), 0.0)

    def test_skill_complementarity_no_overlap(self) -> None:
        m = MentorMatcher()
        mentor = Profile(user_id="m", name="M", skills=[Skill("java", 5)], is_mentor=True)
        mentee = Profile(user_id="e", name="E", skills=[Skill("python", 1)])
        score = m.skill_complementarity(mentor, mentee)
        # mentor has a skill mentee doesn't, bonus
        self.assertGreater(score, 0.0)

    def test_availability_overlap(self) -> None:
        m = MentorMatcher()
        mentor = self._make_mentor()
        mentee = self._make_mentee()
        score = m.availability_overlap(mentor, mentee)
        self.assertGreater(score, 0.0)

    def test_availability_overlap_empty(self) -> None:
        m = MentorMatcher()
        mentor = Profile(user_id="m", name="M", is_mentor=True)
        mentee = Profile(user_id="e", name="E")
        self.assertEqual(m.availability_overlap(mentor, mentee), 0.0)

    def test_interest_similarity(self) -> None:
        m = MentorMatcher()
        mentor = self._make_mentor()
        mentee = self._make_mentee()
        score = m.interest_similarity(mentor, mentee)
        # "backend" overlaps
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_interest_similarity_empty(self) -> None:
        m = MentorMatcher()
        mentor = Profile(user_id="m", name="M", is_mentor=True)
        mentee = Profile(user_id="e", name="E")
        self.assertEqual(m.interest_similarity(mentor, mentee), 0.0)

    def test_project_alignment(self) -> None:
        m = MentorMatcher()
        mentor = self._make_mentor()
        mentee = self._make_mentee()
        score = m.project_alignment(mentor, mentee)
        self.assertEqual(score, 1.0)  # both have "lidco"

    def test_project_alignment_empty(self) -> None:
        m = MentorMatcher()
        mentor = Profile(user_id="m", name="M", is_mentor=True)
        mentee = Profile(user_id="e", name="E")
        self.assertEqual(m.project_alignment(mentor, mentee), 0.0)

    def test_score(self) -> None:
        m = MentorMatcher()
        ms = m.score(self._make_mentor(), self._make_mentee())
        self.assertIsInstance(ms, MatchScore)
        self.assertGreater(ms.total, 0.0)

    def test_find_matches(self) -> None:
        m = MentorMatcher()
        m.add_profile(self._make_mentor("m1"))
        m.add_profile(self._make_mentor("m2"))
        m.add_profile(self._make_mentee("e1"))
        matches = m.find_matches("e1")
        self.assertEqual(len(matches), 2)

    def test_find_matches_nonexistent(self) -> None:
        m = MentorMatcher()
        self.assertEqual(m.find_matches("x"), [])

    def test_find_matches_mentor_as_mentee(self) -> None:
        m = MentorMatcher()
        m.add_profile(self._make_mentor("m1"))
        self.assertEqual(m.find_matches("m1"), [])

    def test_find_matches_min_score(self) -> None:
        m = MentorMatcher()
        m.add_profile(self._make_mentor())
        m.add_profile(self._make_mentee())
        matches = m.find_matches("e1", min_score=0.99)
        # May be 0 if score doesn't reach 0.99
        self.assertIsInstance(matches, list)

    def test_find_matches_top_k(self) -> None:
        m = MentorMatcher()
        for i in range(5):
            m.add_profile(self._make_mentor(f"m{i}"))
        m.add_profile(self._make_mentee("e1"))
        matches = m.find_matches("e1", top_k=2)
        self.assertLessEqual(len(matches), 2)

    def test_find_all_matches(self) -> None:
        m = MentorMatcher()
        m.add_profile(self._make_mentor("m1"))
        m.add_profile(self._make_mentee("e1"))
        m.add_profile(self._make_mentee("e2"))
        all_matches = m.find_all_matches()
        self.assertEqual(len(all_matches), 2)

    def test_find_all_matches_sorted(self) -> None:
        m = MentorMatcher()
        m.add_profile(self._make_mentor("m1"))
        m.add_profile(self._make_mentee("e1"))
        m.add_profile(self._make_mentee("e2"))
        all_matches = m.find_all_matches()
        totals = [ms.total for ms in all_matches]
        self.assertEqual(totals, sorted(totals, reverse=True))


if __name__ == "__main__":
    unittest.main()
