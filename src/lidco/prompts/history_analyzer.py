"""Prompt history analyzer — task 1099.

Extracts patterns, frequent commands, time distributions, and workflow
chains from a sequence of past prompts.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptPattern:
    """An immutable description of a recurring prompt pattern."""

    pattern: str
    frequency: int
    examples: tuple[str, ...]
    category: str


class HistoryAnalyzer:
    """Analyze prompt history for patterns and usage trends.

    Usage::

        analyzer = HistoryAnalyzer(("fix bug", "run tests", "fix bug"))
        patterns = analyzer.analyze()
    """

    _CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
        "fix": ("fix", "patch", "resolve", "repair", "debug"),
        "test": ("test", "spec", "coverage", "assert"),
        "create": ("create", "add", "write", "implement", "generate"),
        "review": ("review", "check", "inspect", "analyze", "lint"),
        "refactor": ("refactor", "rename", "extract", "move", "clean"),
        "docs": ("doc", "readme", "comment", "explain"),
        "navigation": ("find", "search", "list", "show", "goto"),
    }

    def __init__(self, history: tuple[str, ...] = ()) -> None:
        self._history = history

    @property
    def history(self) -> tuple[str, ...]:
        return self._history

    # -- public API ----------------------------------------------------------

    def analyze(self) -> tuple[PromptPattern, ...]:
        """Return patterns ordered by frequency (descending)."""
        if not self._history:
            return ()

        category_map: dict[str, list[str]] = {}
        for prompt in self._history:
            cat = self._categorize(prompt)
            category_map.setdefault(cat, []).append(prompt)

        patterns: list[PromptPattern] = []
        for cat, examples in sorted(
            category_map.items(), key=lambda kv: -len(kv[1])
        ):
            patterns.append(
                PromptPattern(
                    pattern=cat,
                    frequency=len(examples),
                    examples=tuple(dict.fromkeys(examples)),  # unique, order-preserved
                    category=cat,
                )
            )
        return tuple(patterns)

    def frequent_commands(self, n: int = 10) -> tuple[str, ...]:
        """Return up to *n* most-frequent exact prompts."""
        if not self._history or n <= 0:
            return ()
        counter = Counter(self._history)
        return tuple(cmd for cmd, _ in counter.most_common(n))

    def time_patterns(self, timestamps: tuple[str, ...]) -> dict[str, int]:
        """Bucket prompt counts by hour extracted from ISO-like timestamps.

        Each timestamp is expected to contain an ``HH:`` hour segment
        (e.g. ``"2026-03-31T14:30:00"``).  Non-parseable entries are ignored.
        """
        hour_re = re.compile(r"(\d{2}):\d{2}")
        counts: dict[str, int] = {}
        for ts in timestamps:
            m = hour_re.search(ts)
            if m:
                hour = m.group(1)
                counts[hour] = counts.get(hour, 0) + 1
        return counts

    def workflow_chains(self) -> tuple[tuple[str, ...], ...]:
        """Detect consecutive same-category runs as workflow chains.

        Returns a tuple of chains, where each chain is a tuple of prompts
        that share the same category and appear consecutively.
        """
        if not self._history:
            return ()

        chains: list[tuple[str, ...]] = []
        current: list[str] = []
        prev_cat: str | None = None

        for prompt in self._history:
            cat = self._categorize(prompt)
            if cat == prev_cat:
                current.append(prompt)
            else:
                if len(current) >= 2:
                    chains.append(tuple(current))
                current = [prompt]
                prev_cat = cat

        if len(current) >= 2:
            chains.append(tuple(current))

        return tuple(chains)

    # -- internals -----------------------------------------------------------

    def _categorize(self, prompt: str) -> str:
        lower = prompt.lower()
        for cat, keywords in self._CATEGORY_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return cat
        return "other"
