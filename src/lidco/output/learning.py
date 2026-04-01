"""Learning output style — task 1074.

Adds quiz prompts, hints, and educational scaffolding to output.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Quiz:
    """An immutable quiz question with options and explanation."""

    question: str
    options: tuple[str, ...]
    answer_index: int
    explanation: str


class LearningStyle:
    """Output style that turns responses into learning opportunities."""

    @property
    def name(self) -> str:
        return "learning"

    def transform(self, text: str) -> str:
        """Append a learning prompt to non-empty text."""
        if not text.strip():
            return text
        return f"{text}\n\n> Hint: try to predict what this does before reading on."

    def wrap_response(self, response: str) -> str:
        """Wrap response with educational framing."""
        if not response.strip():
            return response
        return (
            "--- Learning Mode ---\n"
            f"{response}\n"
            "--- End Learning Mode ---"
        )

    def generate_quiz(self, topic: str, code: str) -> Quiz:
        """Generate a quiz about *topic* using *code* as context.

        Returns a frozen ``Quiz`` dataclass.
        """
        question = f"What does the following code related to '{topic}' do?"
        options = (
            f"It processes {topic} data",
            f"It validates {topic} input",
            f"It transforms {topic} output",
            f"It caches {topic} results",
        )
        return Quiz(
            question=question,
            options=options,
            answer_index=0,
            explanation=f"The code processes {topic} data as shown:\n{code}",
        )

    def progressive_hint(self, problem: str, level: int) -> str:
        """Return a hint for *problem* at the given *level* (0=vague, 3=explicit).

        Parameters
        ----------
        problem:
            Description of the problem to hint at.
        level:
            Hint specificity from 0 (most vague) to 3 (most explicit).
        """
        if level <= 0:
            return f"Think about what '{problem}' involves at a high level."
        if level == 1:
            return f"Consider the inputs and outputs related to '{problem}'."
        if level == 2:
            return f"Focus on the key operation in '{problem}' — what transforms what?"
        return f"Direct answer: the solution to '{problem}' involves applying the core transformation step by step."
