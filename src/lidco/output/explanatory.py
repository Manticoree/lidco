"""Explanatory output style — task 1073.

Adds contextual "Why:" sections and choice explanations to output.
"""
from __future__ import annotations


class ExplanatoryStyle:
    """Output style that adds explanatory context to responses."""

    @property
    def name(self) -> str:
        return "explanatory"

    def transform(self, text: str) -> str:
        """Add a 'Why:' preamble when the text looks like a decision or action."""
        if not text.strip():
            return text
        lines = text.splitlines()
        first = lines[0].strip().lower()
        triggers = ("changed", "added", "removed", "updated", "created", "deleted", "fixed")
        if any(first.startswith(t) for t in triggers):
            return f"Why: this change was applied because it improves the codebase.\n\n{text}"
        return text

    def wrap_response(self, response: str) -> str:
        """Wrap the full response with an explanatory footer."""
        if not response.strip():
            return response
        return f"{response}\n\n---\n[Explanatory mode: reasoning shown above]"

    def add_context(self, text: str, context_type: str) -> str:
        """Annotate *text* with a context label of *context_type*.

        Parameters
        ----------
        text:
            The content to annotate.
        context_type:
            One of ``"rationale"``, ``"tradeoff"``, ``"alternative"``, or
            any free-form label.
        """
        if not text.strip():
            return text
        label = context_type.capitalize()
        return f"[{label}] {text}"

    def explain_choice(self, choice: str, alternatives: tuple[str, ...]) -> str:
        """Explain why *choice* was selected over *alternatives*.

        Returns a formatted explanation string.
        """
        if not alternatives:
            return f"Chose: {choice} (no alternatives considered)."
        alt_list = ", ".join(alternatives)
        return (
            f"Chose: {choice}\n"
            f"Alternatives considered: {alt_list}\n"
            f"Reason: {choice} was the best fit for the current context."
        )
