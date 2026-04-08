"""Tests for src/lidco/onboard/explainer.py — ConceptExplainer."""

from __future__ import annotations

import unittest

from lidco.onboard.explainer import (
    Concept,
    ConceptExplainer,
    Difficulty,
    Example,
    GlossaryEntry,
    QuizQuestion,
)


class TestDifficulty(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(Difficulty.BEGINNER.value, "beginner")
        self.assertEqual(Difficulty.INTERMEDIATE.value, "intermediate")
        self.assertEqual(Difficulty.ADVANCED.value, "advanced")


class TestQuizQuestion(unittest.TestCase):
    def test_correct_answer(self) -> None:
        q = QuizQuestion(question="What?", choices=["A", "B", "C"], answer_index=1)
        self.assertEqual(q.correct_answer(), "B")

    def test_correct_answer_empty_choices(self) -> None:
        q = QuizQuestion(question="What?")
        self.assertEqual(q.correct_answer(), "")

    def test_correct_answer_out_of_range(self) -> None:
        q = QuizQuestion(question="What?", choices=["A"], answer_index=5)
        self.assertEqual(q.correct_answer(), "")


class TestConcept(unittest.TestCase):
    def test_defaults(self) -> None:
        c = Concept(name="test", summary="A test concept")
        self.assertEqual(c.difficulty, Difficulty.BEGINNER)
        self.assertEqual(c.examples, [])
        self.assertEqual(c.quiz, [])
        self.assertEqual(c.tags, [])
        self.assertEqual(c.prerequisites, [])

    def test_frozen(self) -> None:
        c = Concept(name="x", summary="y")
        with self.assertRaises(AttributeError):
            c.name = "z"  # type: ignore[misc]


class TestConceptExplainer(unittest.TestCase):
    def _make_explainer(self) -> ConceptExplainer:
        exp = ConceptExplainer()
        exp.add_concept(Concept(
            name="sessions",
            summary="Session management",
            difficulty=Difficulty.BEGINNER,
            explanation="Sessions track user state.",
            tags=["core", "state"],
            prerequisites=[],
            examples=[Example(title="Basic", code="s = Session()", explanation="Create session")],
            quiz=[QuizQuestion(question="What is a session?", choices=["State", "File"], answer_index=0)],
        ))
        exp.add_concept(Concept(
            name="agents",
            summary="Agent orchestration",
            difficulty=Difficulty.ADVANCED,
            tags=["ai"],
        ))
        exp.add_concept(Concept(
            name="tools",
            summary="Tool registry",
            difficulty=Difficulty.INTERMEDIATE,
            tags=["core"],
        ))
        return exp

    def test_add_and_count(self) -> None:
        exp = self._make_explainer()
        self.assertEqual(exp.concept_count, 3)

    def test_add_concepts(self) -> None:
        exp = ConceptExplainer()
        exp.add_concepts([
            Concept(name="a", summary="A"),
            Concept(name="b", summary="B"),
        ])
        self.assertEqual(exp.concept_count, 2)

    def test_get_concept(self) -> None:
        exp = self._make_explainer()
        c = exp.get_concept("sessions")
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "sessions")

    def test_get_concept_missing(self) -> None:
        exp = self._make_explainer()
        self.assertIsNone(exp.get_concept("missing"))

    def test_list_concepts_all(self) -> None:
        exp = self._make_explainer()
        concepts = exp.list_concepts()
        self.assertEqual(len(concepts), 3)
        # sorted by name
        self.assertEqual(concepts[0].name, "agents")

    def test_list_concepts_by_difficulty(self) -> None:
        exp = self._make_explainer()
        beginners = exp.list_concepts(Difficulty.BEGINNER)
        self.assertEqual(len(beginners), 1)
        self.assertEqual(beginners[0].name, "sessions")

    def test_search_by_name(self) -> None:
        exp = self._make_explainer()
        results = exp.search_concepts("sess")
        self.assertEqual(len(results), 1)

    def test_search_by_tag(self) -> None:
        exp = self._make_explainer()
        results = exp.search_concepts("core")
        self.assertEqual(len(results), 2)

    def test_search_no_results(self) -> None:
        exp = self._make_explainer()
        results = exp.search_concepts("zzz")
        self.assertEqual(results, [])

    def test_explain(self) -> None:
        exp = self._make_explainer()
        text = exp.explain("sessions")
        self.assertIsNotNone(text)
        self.assertIn("# sessions", text)
        self.assertIn("beginner", text)
        self.assertIn("Session management", text)
        self.assertIn("Example: Basic", text)

    def test_explain_missing(self) -> None:
        exp = self._make_explainer()
        self.assertIsNone(exp.explain("missing"))

    def test_quiz(self) -> None:
        exp = self._make_explainer()
        questions = exp.quiz("sessions")
        self.assertEqual(len(questions), 1)

    def test_quiz_missing(self) -> None:
        exp = self._make_explainer()
        self.assertEqual(exp.quiz("missing"), [])

    def test_check_answer_correct(self) -> None:
        exp = self._make_explainer()
        self.assertTrue(exp.check_answer("sessions", 0, 0))

    def test_check_answer_wrong(self) -> None:
        exp = self._make_explainer()
        self.assertFalse(exp.check_answer("sessions", 0, 1))

    def test_check_answer_missing_concept(self) -> None:
        exp = self._make_explainer()
        self.assertIsNone(exp.check_answer("missing", 0, 0))

    def test_check_answer_bad_index(self) -> None:
        exp = self._make_explainer()
        self.assertIsNone(exp.check_answer("sessions", 99, 0))

    def test_glossary(self) -> None:
        exp = self._make_explainer()
        exp.add_glossary(GlossaryEntry(term="LLM", definition="Large Language Model", see_also=["AI"]))
        exp.add_glossary(GlossaryEntry(term="CLI", definition="Command Line Interface"))
        self.assertEqual(exp.glossary_count, 2)
        entry = exp.get_glossary("LLM")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.definition, "Large Language Model")
        self.assertIsNone(exp.get_glossary("missing"))

    def test_list_glossary(self) -> None:
        exp = ConceptExplainer()
        exp.add_glossary(GlossaryEntry(term="Z", definition="last"))
        exp.add_glossary(GlossaryEntry(term="A", definition="first"))
        entries = exp.list_glossary()
        self.assertEqual(entries[0].term, "A")

    def test_progressive_path(self) -> None:
        exp = self._make_explainer()
        path = exp.progressive_path()
        self.assertEqual(len(path), 3)
        self.assertEqual(path[0].difficulty, Difficulty.BEGINNER)
        self.assertEqual(path[-1].difficulty, Difficulty.ADVANCED)

    def test_summary(self) -> None:
        exp = self._make_explainer()
        exp.add_glossary(GlossaryEntry(term="X", definition="Y"))
        s = exp.summary()
        self.assertIn("3 concepts", s)
        self.assertIn("1 glossary", s)


if __name__ == "__main__":
    unittest.main()
