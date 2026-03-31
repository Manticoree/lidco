"""Q131: Few-shot example selection and formatting."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FewShotExample:
    input: str
    output: str
    description: str = ""


class FewShotSelector:
    """Select and format few-shot examples for prompts."""

    def __init__(self, examples: list[FewShotExample] | None = None) -> None:
        self._examples: list[FewShotExample] = list(examples) if examples else []

    def add(self, example: FewShotExample) -> None:
        self._examples.append(example)

    def select(self, query: str, n: int = 3) -> list[FewShotExample]:
        """Return up to *n* examples ranked by number of query words found in input."""
        query_words = set(query.lower().split())
        if not query_words:
            return list(self._examples[:n])

        def score(ex: FewShotExample) -> int:
            inp_words = set(ex.input.lower().split())
            return len(query_words & inp_words)

        ranked = sorted(self._examples, key=score, reverse=True)
        return ranked[:n]

    def format(self, examples: list[FewShotExample], style: str = "qa") -> str:
        """Format examples as a string.

        style="qa"  → "Q: ...\nA: ..."
        style="xml" → "<example><input>...</input><output>...</output></example>"
        """
        parts: list[str] = []
        for ex in examples:
            if style == "xml":
                parts.append(
                    f"<example><input>{ex.input}</input><output>{ex.output}</output></example>"
                )
            else:
                parts.append(f"Q: {ex.input}\nA: {ex.output}")
        return "\n\n".join(parts)

    def load_from_dict(self, data: list[dict]) -> None:
        """Load examples from a list of dicts with 'input' and 'output' keys."""
        for item in data:
            self._examples.append(
                FewShotExample(
                    input=item.get("input", ""),
                    output=item.get("output", ""),
                    description=item.get("description", ""),
                )
            )
