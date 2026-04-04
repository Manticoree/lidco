"""SubtaskGenerator — decompose goals into subtasks with dependencies."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from lidco.goals.parser import Goal


@dataclass
class Subtask:
    """A single actionable subtask derived from a goal."""

    id: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    effort_estimate: float = 1.0  # story-points / hours (abstract)


class SubtaskGenerator:
    """Decompose a :class:`Goal` into a list of :class:`Subtask` items."""

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate(self, goal: Goal) -> list[Subtask]:
        """Generate subtasks from *goal*.

        Each acceptance criterion becomes a subtask.  If the goal has no
        criteria, a single subtask is created from the goal name.  Subtasks
        are chained linearly (each depends on the previous).
        """
        if not goal.acceptance_criteria:
            st = Subtask(
                id=self._make_id(goal.name, 0),
                description=goal.name or "Complete goal",
                depends_on=[],
                effort_estimate=self._estimate_effort(goal.name),
            )
            return [st]

        subtasks: list[Subtask] = []
        for idx, criterion in enumerate(goal.acceptance_criteria):
            deps = [subtasks[idx - 1].id] if idx > 0 else []
            st = Subtask(
                id=self._make_id(criterion, idx),
                description=criterion,
                depends_on=deps,
                effort_estimate=self._estimate_effort(criterion),
            )
            subtasks.append(st)
        return subtasks

    def dependency_graph(self, subtasks: list[Subtask]) -> dict[str, list[str]]:
        """Return an adjacency list ``{id: [dependency_ids]}``."""
        return {st.id: list(st.depends_on) for st in subtasks}

    def estimate_effort(self, subtasks: list[Subtask]) -> float:
        """Return total effort estimate across all *subtasks*."""
        return sum(st.effort_estimate for st in subtasks)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_id(text: str, index: int) -> str:
        digest = hashlib.md5(f"{text}:{index}".encode()).hexdigest()[:8]
        return f"st-{digest}"

    @staticmethod
    def _estimate_effort(description: str) -> float:
        """Heuristic effort estimate based on description length."""
        words = len(description.split())
        if words <= 5:
            return 1.0
        if words <= 15:
            return 2.0
        return 3.0
