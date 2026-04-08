"""Concept Explainer — explain project concepts with progressive difficulty,
examples, quizzes, and glossary.

Part of Q330 — Onboarding Intelligence (task 1763).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


class Difficulty(Enum):
    """Concept difficulty level."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class Example:
    """An illustrative example for a concept."""

    title: str
    code: str
    explanation: str = ""


@dataclass(frozen=True)
class QuizQuestion:
    """A quiz question for a concept."""

    question: str
    choices: List[str] = field(default_factory=list)
    answer_index: int = 0

    def correct_answer(self) -> str:
        if not self.choices or self.answer_index >= len(self.choices):
            return ""
        return self.choices[self.answer_index]


@dataclass(frozen=True)
class Concept:
    """A project concept to be explained."""

    name: str
    summary: str
    difficulty: Difficulty = Difficulty.BEGINNER
    explanation: str = ""
    examples: List[Example] = field(default_factory=list)
    quiz: List[QuizQuestion] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class GlossaryEntry:
    """A glossary term and definition."""

    term: str
    definition: str
    see_also: List[str] = field(default_factory=list)


class ConceptExplainer:
    """Explain project concepts with progressive difficulty, examples, quizzes, glossary."""

    def __init__(self) -> None:
        self._concepts: Dict[str, Concept] = {}
        self._glossary: Dict[str, GlossaryEntry] = {}

    @property
    def concept_count(self) -> int:
        return len(self._concepts)

    @property
    def glossary_count(self) -> int:
        return len(self._glossary)

    def add_concept(self, concept: Concept) -> None:
        """Add a concept."""
        self._concepts = {**self._concepts, concept.name: concept}

    def add_concepts(self, concepts: Sequence[Concept]) -> None:
        """Add multiple concepts."""
        for c in concepts:
            self.add_concept(c)

    def get_concept(self, name: str) -> Optional[Concept]:
        """Retrieve a concept by name."""
        return self._concepts.get(name)

    def list_concepts(self, difficulty: Optional[Difficulty] = None) -> List[Concept]:
        """List concepts, optionally filtered by difficulty."""
        all_concepts = sorted(self._concepts.values(), key=lambda c: c.name)
        if difficulty is not None:
            return [c for c in all_concepts if c.difficulty == difficulty]
        return all_concepts

    def search_concepts(self, query: str) -> List[Concept]:
        """Search concepts by name, summary, or tags."""
        q = query.lower()
        results: List[Concept] = []
        for c in self._concepts.values():
            if (
                q in c.name.lower()
                or q in c.summary.lower()
                or any(q in t.lower() for t in c.tags)
            ):
                results = [*results, c]
        return sorted(results, key=lambda c: c.name)

    def explain(self, name: str) -> Optional[str]:
        """Return a full explanation string for a concept."""
        concept = self._concepts.get(name)
        if concept is None:
            return None
        lines = [
            f"# {concept.name}",
            f"Difficulty: {concept.difficulty.value}",
            "",
            concept.summary,
        ]
        if concept.explanation:
            lines.extend(["", concept.explanation])
        if concept.prerequisites:
            lines.extend(["", "Prerequisites: " + ", ".join(concept.prerequisites)])
        if concept.examples:
            lines.append("")
            for ex in concept.examples:
                lines.append(f"## Example: {ex.title}")
                lines.append(ex.code)
                if ex.explanation:
                    lines.append(ex.explanation)
        return "\n".join(lines)

    def quiz(self, name: str) -> List[QuizQuestion]:
        """Return quiz questions for a concept."""
        concept = self._concepts.get(name)
        if concept is None:
            return []
        return list(concept.quiz)

    def check_answer(self, name: str, question_index: int, answer_index: int) -> Optional[bool]:
        """Check if an answer is correct. Returns None if concept/question not found."""
        concept = self._concepts.get(name)
        if concept is None:
            return None
        if question_index < 0 or question_index >= len(concept.quiz):
            return None
        return concept.quiz[question_index].answer_index == answer_index

    def add_glossary(self, entry: GlossaryEntry) -> None:
        """Add a glossary entry."""
        self._glossary = {**self._glossary, entry.term: entry}

    def get_glossary(self, term: str) -> Optional[GlossaryEntry]:
        """Look up a glossary entry."""
        return self._glossary.get(term)

    def list_glossary(self) -> List[GlossaryEntry]:
        """Return all glossary entries sorted by term."""
        return sorted(self._glossary.values(), key=lambda e: e.term)

    def progressive_path(self) -> List[Concept]:
        """Return concepts ordered by progressive difficulty."""
        order = {Difficulty.BEGINNER: 0, Difficulty.INTERMEDIATE: 1, Difficulty.ADVANCED: 2}
        return sorted(
            self._concepts.values(),
            key=lambda c: (order.get(c.difficulty, 99), c.name),
        )

    def summary(self) -> str:
        """Return a human-readable summary."""
        by_diff: Dict[str, int] = {}
        for c in self._concepts.values():
            key = c.difficulty.value
            by_diff = {**by_diff, key: by_diff.get(key, 0) + 1}
        lines = [
            f"Concept Explainer: {self.concept_count} concepts, {self.glossary_count} glossary entries",
        ]
        for d in ["beginner", "intermediate", "advanced"]:
            if d in by_diff:
                lines.append(f"  {d}: {by_diff[d]}")
        return "\n".join(lines)
