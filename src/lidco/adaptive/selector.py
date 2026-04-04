"""ExampleSelector — select best few-shot examples for a task."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class Example:
    """A few-shot example with metadata."""

    input_text: str
    output_text: str
    task_type: str = "general"
    difficulty: int = 1  # 1=easy, 2=medium, 3=hard
    tags: list[str] = field(default_factory=list)


class ExampleSelector:
    """Select best few-shot examples from a pool."""

    def __init__(self) -> None:
        self._examples: list[Example] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_example(self, example: Example) -> None:
        """Add an example to the pool."""
        self._examples.append(example)

    def examples(self) -> list[Example]:
        """Return all stored examples."""
        return list(self._examples)

    def clear(self) -> None:
        """Remove all examples."""
        self._examples.clear()

    def select(
        self,
        task_type: str,
        k: int = 3,
        *,
        difficulty: int | None = None,
        tags: Sequence[str] = (),
    ) -> list[Example]:
        """Select up to *k* best examples for *task_type*.

        Scoring:
        - +3 if task_type matches
        - +2 if difficulty matches (when specified)
        - +1 per matching tag
        Then diverse: no two examples with identical input_text.
        """
        scored: list[tuple[float, int, Example]] = []
        for idx, ex in enumerate(self._examples):
            score = 0.0
            if ex.task_type == task_type:
                score += 3.0
            if difficulty is not None and ex.difficulty == difficulty:
                score += 2.0
            if tags:
                tag_set = set(tags)
                score += len(tag_set & set(ex.tags))
            scored.append((score, idx, ex))

        # Sort by score desc, then original order for stability
        scored.sort(key=lambda t: (-t[0], t[1]))

        # Diversity: skip duplicates by input_text
        seen_inputs: set[str] = set()
        result: list[Example] = []
        for _, _, ex in scored:
            if ex.input_text in seen_inputs:
                continue
            seen_inputs.add(ex.input_text)
            result.append(ex)
            if len(result) >= k:
                break
        return result
