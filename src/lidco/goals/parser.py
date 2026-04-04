"""GoalParser — parse natural language goals into structured objectives."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Goal:
    """Structured representation of a user goal."""

    name: str
    acceptance_criteria: list[str] = field(default_factory=list)
    priority: str = "medium"  # low | medium | high | critical


class GoalParser:
    """Parse free-form text into :class:`Goal` objects."""

    _PRIORITY_KEYWORDS: dict[str, str] = {
        "critical": "critical",
        "urgent": "critical",
        "asap": "critical",
        "high": "high",
        "important": "high",
        "medium": "medium",
        "normal": "medium",
        "low": "low",
        "minor": "low",
        "nice to have": "low",
    }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def parse(self, text: str) -> Goal:
        """Parse *text* into a :class:`Goal`.

        The first sentence (or the whole text if short) becomes the name.
        Bullet items starting with ``-`` or ``*`` become acceptance criteria.
        Priority is inferred from keywords.
        """
        if not text or not text.strip():
            return Goal(name="", acceptance_criteria=[], priority="medium")

        text = text.strip()
        name = self._extract_name(text)
        criteria = self.extract_criteria(text)
        priority = self._infer_priority(text)
        return Goal(name=name, acceptance_criteria=criteria, priority=priority)

    def extract_criteria(self, text: str) -> list[str]:
        """Extract acceptance criteria from bullet lists in *text*.

        Lines starting with ``- `` or ``* `` are considered criteria.
        Lines starting with a digit followed by ``.`` or ``)`` are also included.
        """
        criteria: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            # bullet lists
            if stripped.startswith("- ") or stripped.startswith("* "):
                criteria.append(stripped[2:].strip())
            # numbered lists
            elif re.match(r"^\d+[.)]\s+", stripped):
                criteria.append(re.sub(r"^\d+[.)]\s+", "", stripped).strip())
        return criteria

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _extract_name(self, text: str) -> str:
        """Return the first meaningful sentence as the goal name."""
        # Take first line, or up to first period
        first_line = text.split("\n")[0].strip()
        # Remove bullet prefix if present
        first_line = re.sub(r"^[-*]\s+", "", first_line)
        first_line = re.sub(r"^\d+[.)]\s+", "", first_line)
        # Trim at sentence boundary if long
        match = re.match(r"^(.+?[.!?])\s", first_line)
        if match:
            return match.group(1).strip()
        return first_line.strip()

    def _infer_priority(self, text: str) -> str:
        lower = text.lower()
        for keyword, priority in self._PRIORITY_KEYWORDS.items():
            if keyword in lower:
                return priority
        return "medium"
