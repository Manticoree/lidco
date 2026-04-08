"""Code Walkthrough — Guided step-by-step code walkthroughs.

Navigate code with questions, key concepts, and bookmarks.
Pure stdlib, no external dependencies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KeyConcept:
    """A key concept identified in the code."""

    name: str
    description: str
    line_start: int = 0
    line_end: int = 0


@dataclass(frozen=True)
class Bookmark:
    """A bookmarked section of code."""

    label: str
    file_path: str
    line_start: int
    line_end: int
    note: str = ""


@dataclass(frozen=True)
class Question:
    """A comprehension question about the code."""

    text: str
    hint: str = ""
    answer: str = ""
    difficulty: int = 1  # 1..3


@dataclass
class WalkthroughStep:
    """A single step in a code walkthrough."""

    step_number: int
    title: str
    description: str
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    code_snippet: str = ""
    concepts: list[KeyConcept] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)


@dataclass
class Walkthrough:
    """A complete code walkthrough session."""

    walkthrough_id: str
    title: str
    description: str = ""
    steps: list[WalkthroughStep] = field(default_factory=list)
    bookmarks: list[Bookmark] = field(default_factory=list)
    current_step: int = 0
    created_at: float = field(default_factory=time.time)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def is_complete(self) -> bool:
        return self.current_step >= self.total_steps and self.total_steps > 0

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        return min(1.0, self.current_step / self.total_steps)

    def get_current_step(self) -> WalkthroughStep | None:
        if 0 <= self.current_step < self.total_steps:
            return self.steps[self.current_step]
        return None


# ---------------------------------------------------------------------------
# WalkthroughManager
# ---------------------------------------------------------------------------

class WalkthroughManager:
    """Create and navigate guided code walkthroughs."""

    def __init__(self) -> None:
        self._walkthroughs: dict[str, Walkthrough] = {}
        self._counter: int = 0

    # -- Create --------------------------------------------------------------

    def create(self, title: str, description: str = "") -> Walkthrough:
        """Create a new walkthrough."""
        self._counter += 1
        wid = f"wt-{self._counter}"
        wt = Walkthrough(walkthrough_id=wid, title=title, description=description)
        self._walkthroughs[wid] = wt
        return wt

    def get(self, walkthrough_id: str) -> Walkthrough | None:
        return self._walkthroughs.get(walkthrough_id)

    @property
    def walkthroughs(self) -> list[Walkthrough]:
        return list(self._walkthroughs.values())

    def remove(self, walkthrough_id: str) -> bool:
        return self._walkthroughs.pop(walkthrough_id, None) is not None

    # -- Steps ---------------------------------------------------------------

    def add_step(
        self,
        walkthrough_id: str,
        title: str,
        description: str,
        *,
        file_path: str = "",
        line_start: int = 0,
        line_end: int = 0,
        code_snippet: str = "",
    ) -> WalkthroughStep | None:
        """Add a step to a walkthrough. Returns the step or None if not found."""
        wt = self._walkthroughs.get(walkthrough_id)
        if wt is None:
            return None

        step = WalkthroughStep(
            step_number=len(wt.steps) + 1,
            title=title,
            description=description,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            code_snippet=code_snippet,
        )
        wt.steps.append(step)
        return step

    def add_concept(
        self,
        walkthrough_id: str,
        step_number: int,
        name: str,
        description: str,
        *,
        line_start: int = 0,
        line_end: int = 0,
    ) -> KeyConcept | None:
        """Add a key concept to a step."""
        wt = self._walkthroughs.get(walkthrough_id)
        if wt is None:
            return None

        idx = step_number - 1
        if idx < 0 or idx >= len(wt.steps):
            return None

        concept = KeyConcept(
            name=name, description=description,
            line_start=line_start, line_end=line_end,
        )
        wt.steps[idx].concepts.append(concept)
        return concept

    def add_question(
        self,
        walkthrough_id: str,
        step_number: int,
        text: str,
        *,
        hint: str = "",
        answer: str = "",
        difficulty: int = 1,
    ) -> Question | None:
        """Add a comprehension question to a step."""
        wt = self._walkthroughs.get(walkthrough_id)
        if wt is None:
            return None

        idx = step_number - 1
        if idx < 0 or idx >= len(wt.steps):
            return None

        question = Question(text=text, hint=hint, answer=answer, difficulty=difficulty)
        wt.steps[idx].questions.append(question)
        return question

    # -- Navigation ----------------------------------------------------------

    def advance(self, walkthrough_id: str) -> WalkthroughStep | None:
        """Advance to the next step. Returns the new current step or None."""
        wt = self._walkthroughs.get(walkthrough_id)
        if wt is None or wt.is_complete:
            return None

        wt.current_step += 1
        return wt.get_current_step()

    def go_back(self, walkthrough_id: str) -> WalkthroughStep | None:
        """Go back one step. Returns the new current step or None."""
        wt = self._walkthroughs.get(walkthrough_id)
        if wt is None or wt.current_step <= 0:
            return None

        wt.current_step -= 1
        return wt.get_current_step()

    def go_to_step(self, walkthrough_id: str, step_number: int) -> WalkthroughStep | None:
        """Jump to a specific step."""
        wt = self._walkthroughs.get(walkthrough_id)
        if wt is None:
            return None

        idx = step_number - 1
        if idx < 0 or idx >= len(wt.steps):
            return None

        wt.current_step = idx
        return wt.steps[idx]

    # -- Bookmarks -----------------------------------------------------------

    def add_bookmark(
        self,
        walkthrough_id: str,
        label: str,
        file_path: str,
        line_start: int,
        line_end: int,
        *,
        note: str = "",
    ) -> Bookmark | None:
        """Bookmark an important section."""
        wt = self._walkthroughs.get(walkthrough_id)
        if wt is None:
            return None

        bookmark = Bookmark(
            label=label, file_path=file_path,
            line_start=line_start, line_end=line_end,
            note=note,
        )
        wt.bookmarks.append(bookmark)
        return bookmark

    def get_bookmarks(self, walkthrough_id: str) -> list[Bookmark]:
        """Get all bookmarks for a walkthrough."""
        wt = self._walkthroughs.get(walkthrough_id)
        if wt is None:
            return []
        return list(wt.bookmarks)
