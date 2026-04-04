"""AI-assisted conflict resolver — smart resolution strategies (stdlib only)."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from lidco.merge.detector import Conflict


@dataclass
class Resolution:
    """A resolved conflict with chosen text and strategy."""

    conflict: Conflict
    strategy: str  # "ours" | "theirs" | "union" | "smart" | "custom"
    resolved_text: str
    confidence: float = 0.0
    explanation: str = ""


class ConflictResolver:
    """Resolve merge conflicts using heuristic strategies."""

    def resolve(self, conflict: Conflict, strategy: str = "smart") -> Resolution:
        """Resolve a single conflict using the given strategy.

        Strategies:
            ours   — keep text_a
            theirs — keep text_b
            union  — concatenate both
            smart  — heuristic: pick the longer/more complete version
        """
        if strategy == "ours":
            return Resolution(
                conflict=conflict,
                strategy="ours",
                resolved_text=conflict.text_a,
                confidence=1.0,
                explanation="Kept branch A (ours).",
            )
        if strategy == "theirs":
            return Resolution(
                conflict=conflict,
                strategy="theirs",
                resolved_text=conflict.text_b,
                confidence=1.0,
                explanation="Kept branch B (theirs).",
            )
        if strategy == "union":
            combined = conflict.text_a + conflict.text_b
            return Resolution(
                conflict=conflict,
                strategy="union",
                resolved_text=combined,
                confidence=0.7,
                explanation="Combined both versions.",
            )
        # smart — heuristic
        return self._smart_resolve(conflict)

    def suggest(self, conflict: Conflict) -> list[str]:
        """Suggest possible resolution strategies for a conflict."""
        suggestions: list[str] = ["ours", "theirs"]

        ratio = difflib.SequenceMatcher(
            None, conflict.text_a, conflict.text_b
        ).ratio()

        if ratio > 0.8:
            suggestions.insert(0, "smart")
        else:
            suggestions.append("union")
            suggestions.append("smart")

        return suggestions

    def preview(self, conflict: Conflict, choice: str) -> str:
        """Preview the result of applying a resolution strategy."""
        resolution = self.resolve(conflict, strategy=choice)
        lines = [
            f"Strategy: {resolution.strategy}",
            f"Confidence: {resolution.confidence:.1%}",
            f"Explanation: {resolution.explanation}",
            "---",
            resolution.resolved_text,
        ]
        return "\n".join(lines)

    def auto_resolve(self, conflicts: list[Conflict]) -> list[Resolution]:
        """Auto-resolve a batch of conflicts using heuristics.

        Trivial conflicts (identical or whitespace-only) are resolved
        automatically; complex ones use the smart strategy.
        """
        resolutions: list[Resolution] = []
        for conflict in conflicts:
            a_stripped = conflict.text_a.strip()
            b_stripped = conflict.text_b.strip()

            if a_stripped == b_stripped:
                # Whitespace-only difference
                resolutions.append(
                    Resolution(
                        conflict=conflict,
                        strategy="ours",
                        resolved_text=conflict.text_a,
                        confidence=1.0,
                        explanation="Identical after stripping whitespace.",
                    )
                )
            else:
                resolutions.append(self._smart_resolve(conflict))

        return resolutions

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _smart_resolve(self, conflict: Conflict) -> Resolution:
        """Heuristic resolution: prefer the version that adds more content."""
        a_lines = conflict.text_a.splitlines()
        b_lines = conflict.text_b.splitlines()

        # Prefer the version that is a strict superset
        a_set = set(conflict.text_a.splitlines())
        b_set = set(conflict.text_b.splitlines())

        if a_set >= b_set:
            return Resolution(
                conflict=conflict,
                strategy="smart",
                resolved_text=conflict.text_a,
                confidence=0.8,
                explanation="Branch A is a superset of branch B.",
            )
        if b_set >= a_set:
            return Resolution(
                conflict=conflict,
                strategy="smart",
                resolved_text=conflict.text_b,
                confidence=0.8,
                explanation="Branch B is a superset of branch A.",
            )

        # Fall back to longer version
        if len(conflict.text_a) >= len(conflict.text_b):
            return Resolution(
                conflict=conflict,
                strategy="smart",
                resolved_text=conflict.text_a,
                confidence=0.6,
                explanation="Chose longer version (branch A).",
            )
        return Resolution(
            conflict=conflict,
            strategy="smart",
            resolved_text=conflict.text_b,
            confidence=0.6,
            explanation="Chose longer version (branch B).",
        )
