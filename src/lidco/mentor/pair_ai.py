"""Pair Programming AI — AI-assisted pair programming sessions.

Explain while coding, suggest alternatives, identify teaching moments,
and adapt to the learner's level.  Pure stdlib, no external dependencies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


# ---------------------------------------------------------------------------
# Enums & Data classes
# ---------------------------------------------------------------------------

class DifficultyLevel(Enum):
    """Learner difficulty level."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class MomentKind(Enum):
    """Kind of teaching moment."""

    EXPLANATION = "explanation"
    ALTERNATIVE = "alternative"
    BEST_PRACTICE = "best_practice"
    PITFALL = "pitfall"
    PATTERN = "pattern"
    REFACTOR = "refactor"


@dataclass(frozen=True)
class TeachingMoment:
    """A single teaching moment identified during pairing."""

    kind: MomentKind
    title: str
    explanation: str
    code_before: str = ""
    code_after: str = ""
    line: int = 0

    @property
    def has_code(self) -> bool:
        return bool(self.code_before or self.code_after)


@dataclass(frozen=True)
class Alternative:
    """An alternative approach to a code snippet."""

    description: str
    code: str
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Explanation:
    """An explanation of a code construct."""

    construct: str
    summary: str
    detail: str
    difficulty: DifficultyLevel = DifficultyLevel.BEGINNER


@dataclass
class PairSession:
    """A pair programming session."""

    session_id: str
    mentor_name: str = "AI"
    learner_name: str = "User"
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    moments: list[TeachingMoment] = field(default_factory=list)
    explanations: list[Explanation] = field(default_factory=list)
    alternatives: list[Alternative] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    @property
    def duration_seconds(self) -> float:
        end = self.ended_at or time.time()
        return end - self.started_at

    @property
    def summary(self) -> dict[str, int]:
        return {
            "teaching_moments": len(self.moments),
            "explanations": len(self.explanations),
            "alternatives": len(self.alternatives),
        }


# ---------------------------------------------------------------------------
# Built-in construct explanations (language-agnostic basics)
# ---------------------------------------------------------------------------

_BUILTIN_EXPLANATIONS: dict[str, dict[str, str]] = {
    "list_comprehension": {
        "summary": "Creates a new list by transforming each element.",
        "detail": (
            "List comprehensions provide a concise way to create lists. "
            "The syntax is [expression for item in iterable if condition]. "
            "They are generally faster than equivalent for-loops because "
            "the iteration is optimized internally."
        ),
    },
    "decorator": {
        "summary": "Wraps a function to modify its behavior.",
        "detail": (
            "A decorator is a function that takes another function as input "
            "and returns a new function with extended behavior. Use @decorator "
            "syntax above the function definition."
        ),
    },
    "context_manager": {
        "summary": "Manages resource setup and teardown automatically.",
        "detail": (
            "Context managers implement __enter__ and __exit__ methods. "
            "The 'with' statement ensures cleanup runs even if an error occurs. "
            "Common uses: file handling, database connections, locks."
        ),
    },
    "generator": {
        "summary": "Produces values lazily, one at a time.",
        "detail": (
            "Generators use 'yield' instead of 'return'. They produce values "
            "on demand, saving memory for large datasets. Generator expressions "
            "use parentheses: (x for x in range(10))."
        ),
    },
    "async_await": {
        "summary": "Enables non-blocking concurrent execution.",
        "detail": (
            "async/await lets you write asynchronous code that looks synchronous. "
            "'async def' defines a coroutine; 'await' suspends execution until "
            "the awaited coroutine completes."
        ),
    },
}

# ---------------------------------------------------------------------------
# Built-in best practice patterns
# ---------------------------------------------------------------------------

_BEST_PRACTICES: list[dict[str, str]] = [
    {
        "pattern": "early_return",
        "title": "Use early returns to reduce nesting",
        "explanation": "Guard clauses at the top of a function reduce indentation and improve readability.",
    },
    {
        "pattern": "immutability",
        "title": "Prefer immutable data structures",
        "explanation": "Immutable objects are easier to reason about, thread-safe, and prevent accidental mutation.",
    },
    {
        "pattern": "single_responsibility",
        "title": "Each function should do one thing",
        "explanation": "Small, focused functions are easier to test, debug, and reuse.",
    },
    {
        "pattern": "descriptive_names",
        "title": "Use descriptive variable and function names",
        "explanation": "Names should reveal intent. Avoid abbreviations unless universally understood.",
    },
    {
        "pattern": "error_handling",
        "title": "Handle errors explicitly",
        "explanation": "Catch specific exceptions, provide helpful messages, and fail gracefully.",
    },
]


# ---------------------------------------------------------------------------
# PairProgrammingAI
# ---------------------------------------------------------------------------

class PairProgrammingAI:
    """AI pair programming assistant that explains, suggests, and teaches."""

    def __init__(self) -> None:
        self._sessions: dict[str, PairSession] = {}
        self._session_counter: int = 0

    # -- Session management --------------------------------------------------

    def start_session(
        self,
        *,
        learner_name: str = "User",
        difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
    ) -> PairSession:
        """Start a new pair programming session."""
        self._session_counter += 1
        sid = f"pair-{self._session_counter}"
        session = PairSession(
            session_id=sid,
            learner_name=learner_name,
            difficulty=difficulty,
        )
        self._sessions[sid] = session
        return session

    def end_session(self, session_id: str) -> PairSession | None:
        """End a session. Returns the session or None if not found."""
        session = self._sessions.get(session_id)
        if session is not None and session.is_active:
            session.ended_at = time.time()
        return session

    def get_session(self, session_id: str) -> PairSession | None:
        return self._sessions.get(session_id)

    @property
    def active_sessions(self) -> list[PairSession]:
        return [s for s in self._sessions.values() if s.is_active]

    # -- Explain code --------------------------------------------------------

    def explain_construct(
        self,
        construct: str,
        *,
        difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
        session_id: str | None = None,
    ) -> Explanation:
        """Explain a code construct."""
        key = construct.lower().replace(" ", "_").replace("-", "_")
        info = _BUILTIN_EXPLANATIONS.get(key)
        if info:
            explanation = Explanation(
                construct=construct,
                summary=info["summary"],
                detail=info["detail"],
                difficulty=difficulty,
            )
        else:
            explanation = Explanation(
                construct=construct,
                summary=f"Explanation for '{construct}'.",
                detail=f"'{construct}' is a programming concept. Provide more context for a detailed explanation.",
                difficulty=difficulty,
            )

        if session_id:
            session = self._sessions.get(session_id)
            if session:
                session.explanations.append(explanation)

        return explanation

    # -- Suggest alternatives ------------------------------------------------

    def suggest_alternative(
        self,
        code: str,
        description: str = "",
        *,
        session_id: str | None = None,
    ) -> Alternative:
        """Suggest an alternative approach to the given code."""
        alt = Alternative(
            description=description or "Consider an alternative approach.",
            code=code,
            pros=["May improve readability", "Follows common patterns"],
            cons=["Requires review for correctness"],
        )

        if session_id:
            session = self._sessions.get(session_id)
            if session:
                session.alternatives.append(alt)

        return alt

    # -- Teaching moments ----------------------------------------------------

    def add_teaching_moment(
        self,
        kind: MomentKind,
        title: str,
        explanation: str,
        *,
        code_before: str = "",
        code_after: str = "",
        line: int = 0,
        session_id: str | None = None,
    ) -> TeachingMoment:
        """Record a teaching moment."""
        moment = TeachingMoment(
            kind=kind,
            title=title,
            explanation=explanation,
            code_before=code_before,
            code_after=code_after,
            line=line,
        )

        if session_id:
            session = self._sessions.get(session_id)
            if session:
                session.moments.append(moment)

        return moment

    # -- Best practices ------------------------------------------------------

    def get_best_practices(self, pattern: str | None = None) -> list[dict[str, str]]:
        """Get best practice tips, optionally filtered by pattern name."""
        if pattern is None:
            return list(_BEST_PRACTICES)
        key = pattern.lower().replace(" ", "_").replace("-", "_")
        return [bp for bp in _BEST_PRACTICES if bp["pattern"] == key]

    # -- Adaptive difficulty -------------------------------------------------

    def adapt_difficulty(self, session_id: str, new_level: DifficultyLevel) -> bool:
        """Change the difficulty level for a session. Returns True if updated."""
        session = self._sessions.get(session_id)
        if session is None or not session.is_active:
            return False
        session.difficulty = new_level
        return True
