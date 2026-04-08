"""Tests for lidco.mentor.pair_ai — Pair Programming AI."""

from __future__ import annotations

import unittest

from lidco.mentor.pair_ai import (
    Alternative,
    DifficultyLevel,
    Explanation,
    MomentKind,
    PairProgrammingAI,
    PairSession,
    TeachingMoment,
)


class TestTeachingMoment(unittest.TestCase):
    """Tests for TeachingMoment."""

    def test_has_code_true(self) -> None:
        tm = TeachingMoment(MomentKind.EXPLANATION, "T", "E", code_before="x = 1")
        self.assertTrue(tm.has_code)

    def test_has_code_false(self) -> None:
        tm = TeachingMoment(MomentKind.EXPLANATION, "T", "E")
        self.assertFalse(tm.has_code)


class TestPairSession(unittest.TestCase):
    """Tests for PairSession."""

    def test_is_active(self) -> None:
        s = PairSession(session_id="s1")
        self.assertTrue(s.is_active)

    def test_not_active_after_end(self) -> None:
        s = PairSession(session_id="s1", ended_at=1.0)
        self.assertFalse(s.is_active)

    def test_duration_seconds(self) -> None:
        s = PairSession(session_id="s1", started_at=100.0, ended_at=200.0)
        self.assertAlmostEqual(s.duration_seconds, 100.0)

    def test_summary(self) -> None:
        s = PairSession(session_id="s1")
        self.assertEqual(s.summary["teaching_moments"], 0)
        self.assertEqual(s.summary["explanations"], 0)
        self.assertEqual(s.summary["alternatives"], 0)


class TestPairProgrammingAI(unittest.TestCase):
    """Tests for PairProgrammingAI."""

    def test_start_session(self) -> None:
        ai = PairProgrammingAI()
        session = ai.start_session()
        self.assertTrue(session.is_active)
        self.assertEqual(session.difficulty, DifficultyLevel.INTERMEDIATE)

    def test_start_session_custom_difficulty(self) -> None:
        ai = PairProgrammingAI()
        session = ai.start_session(difficulty=DifficultyLevel.BEGINNER)
        self.assertEqual(session.difficulty, DifficultyLevel.BEGINNER)

    def test_start_session_custom_name(self) -> None:
        ai = PairProgrammingAI()
        session = ai.start_session(learner_name="Alice")
        self.assertEqual(session.learner_name, "Alice")

    def test_end_session(self) -> None:
        ai = PairProgrammingAI()
        session = ai.start_session()
        ended = ai.end_session(session.session_id)
        self.assertIsNotNone(ended)
        self.assertFalse(ended.is_active)

    def test_end_session_nonexistent(self) -> None:
        ai = PairProgrammingAI()
        self.assertIsNone(ai.end_session("nope"))

    def test_get_session(self) -> None:
        ai = PairProgrammingAI()
        session = ai.start_session()
        self.assertEqual(ai.get_session(session.session_id), session)

    def test_active_sessions(self) -> None:
        ai = PairProgrammingAI()
        s1 = ai.start_session()
        s2 = ai.start_session()
        ai.end_session(s1.session_id)
        self.assertEqual(len(ai.active_sessions), 1)
        self.assertEqual(ai.active_sessions[0].session_id, s2.session_id)

    def test_explain_known_construct(self) -> None:
        ai = PairProgrammingAI()
        exp = ai.explain_construct("list_comprehension")
        self.assertIn("list", exp.summary.lower())

    def test_explain_unknown_construct(self) -> None:
        ai = PairProgrammingAI()
        exp = ai.explain_construct("foobar_xyz")
        self.assertIn("foobar_xyz", exp.detail)

    def test_explain_with_session(self) -> None:
        ai = PairProgrammingAI()
        session = ai.start_session()
        ai.explain_construct("decorator", session_id=session.session_id)
        self.assertEqual(len(session.explanations), 1)

    def test_explain_with_nonexistent_session(self) -> None:
        ai = PairProgrammingAI()
        exp = ai.explain_construct("decorator", session_id="nope")
        self.assertIsInstance(exp, Explanation)

    def test_suggest_alternative(self) -> None:
        ai = PairProgrammingAI()
        alt = ai.suggest_alternative("x = 1", "Use a constant")
        self.assertEqual(alt.description, "Use a constant")
        self.assertTrue(len(alt.pros) > 0)

    def test_suggest_alternative_default_desc(self) -> None:
        ai = PairProgrammingAI()
        alt = ai.suggest_alternative("x = 1")
        self.assertIn("alternative", alt.description.lower())

    def test_suggest_with_session(self) -> None:
        ai = PairProgrammingAI()
        session = ai.start_session()
        ai.suggest_alternative("x = 1", session_id=session.session_id)
        self.assertEqual(len(session.alternatives), 1)

    def test_add_teaching_moment(self) -> None:
        ai = PairProgrammingAI()
        tm = ai.add_teaching_moment(MomentKind.PITFALL, "Watch out", "Avoid mutation")
        self.assertEqual(tm.kind, MomentKind.PITFALL)
        self.assertEqual(tm.title, "Watch out")

    def test_add_teaching_moment_with_session(self) -> None:
        ai = PairProgrammingAI()
        session = ai.start_session()
        ai.add_teaching_moment(
            MomentKind.BEST_PRACTICE, "T", "E",
            session_id=session.session_id,
        )
        self.assertEqual(len(session.moments), 1)

    def test_add_teaching_moment_with_code(self) -> None:
        ai = PairProgrammingAI()
        tm = ai.add_teaching_moment(
            MomentKind.REFACTOR, "Refactor", "Simplify",
            code_before="x = 1", code_after="X = 1", line=10,
        )
        self.assertTrue(tm.has_code)
        self.assertEqual(tm.line, 10)

    def test_get_best_practices_all(self) -> None:
        ai = PairProgrammingAI()
        bps = ai.get_best_practices()
        self.assertGreater(len(bps), 0)

    def test_get_best_practices_filtered(self) -> None:
        ai = PairProgrammingAI()
        bps = ai.get_best_practices("early_return")
        self.assertEqual(len(bps), 1)

    def test_get_best_practices_no_match(self) -> None:
        ai = PairProgrammingAI()
        bps = ai.get_best_practices("nonexistent_pattern")
        self.assertEqual(len(bps), 0)

    def test_adapt_difficulty(self) -> None:
        ai = PairProgrammingAI()
        session = ai.start_session()
        result = ai.adapt_difficulty(session.session_id, DifficultyLevel.ADVANCED)
        self.assertTrue(result)
        self.assertEqual(session.difficulty, DifficultyLevel.ADVANCED)

    def test_adapt_difficulty_nonexistent(self) -> None:
        ai = PairProgrammingAI()
        self.assertFalse(ai.adapt_difficulty("nope", DifficultyLevel.BEGINNER))

    def test_adapt_difficulty_ended_session(self) -> None:
        ai = PairProgrammingAI()
        session = ai.start_session()
        ai.end_session(session.session_id)
        self.assertFalse(ai.adapt_difficulty(session.session_id, DifficultyLevel.BEGINNER))

    def test_session_ids_unique(self) -> None:
        ai = PairProgrammingAI()
        s1 = ai.start_session()
        s2 = ai.start_session()
        self.assertNotEqual(s1.session_id, s2.session_id)


if __name__ == "__main__":
    unittest.main()
