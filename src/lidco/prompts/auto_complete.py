"""Prompt auto-completion engine — task 1100.

Provides prefix and fuzzy completion across commands, files, and symbols.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Completion:
    """An immutable completion candidate."""

    text: str
    kind: str  # "command" | "file" | "symbol"
    score: float


class AutoComplete:
    """Multi-source auto-completion with prefix and fuzzy matching.

    All mutating operations return a *new* ``AutoComplete`` instance.

    Usage::

        ac = AutoComplete(commands=("/fix", "/test", "/review"))
        results = ac.complete("/fi")
    """

    def __init__(
        self,
        commands: tuple[str, ...] = (),
        files: tuple[str, ...] = (),
        symbols: tuple[str, ...] = (),
    ) -> None:
        self._commands = commands
        self._files = files
        self._symbols = symbols

    # -- properties ----------------------------------------------------------

    @property
    def commands(self) -> tuple[str, ...]:
        return self._commands

    @property
    def files(self) -> tuple[str, ...]:
        return self._files

    @property
    def symbols(self) -> tuple[str, ...]:
        return self._symbols

    # -- public API ----------------------------------------------------------

    def complete(self, prefix: str) -> tuple[Completion, ...]:
        """Return completions matching *prefix*, sorted by score descending."""
        if not prefix:
            return ()

        results: list[Completion] = []

        for cmd in self._commands:
            score = self._score(prefix, cmd)
            if score > 0.0:
                results.append(Completion(text=cmd, kind="command", score=score))

        for f in self._files:
            score = self._score(prefix, f)
            if score > 0.0:
                results.append(Completion(text=f, kind="file", score=score))

        for sym in self._symbols:
            score = self._score(prefix, sym)
            if score > 0.0:
                results.append(Completion(text=sym, kind="symbol", score=score))

        results.sort(key=lambda c: -c.score)
        return tuple(results)

    def add_source(self, kind: str, items: tuple[str, ...]) -> AutoComplete:
        """Return a new ``AutoComplete`` with *items* added to *kind* source."""
        commands = self._commands
        files = self._files
        symbols = self._symbols

        if kind == "command":
            commands = (*commands, *items)
        elif kind == "file":
            files = (*files, *items)
        elif kind == "symbol":
            symbols = (*symbols, *items)
        else:
            raise ValueError(f"Unknown completion kind: {kind!r}")

        return AutoComplete(commands=commands, files=files, symbols=symbols)

    def fuzzy_match(
        self, query: str, candidates: tuple[str, ...]
    ) -> tuple[str, ...]:
        """Return *candidates* that fuzzy-match *query*, best first."""
        if not query:
            return ()

        scored: list[tuple[float, str]] = []
        for cand in candidates:
            score = self._fuzzy_score(query.lower(), cand.lower())
            if score > 0.0:
                scored.append((score, cand))

        scored.sort(key=lambda t: -t[0])
        return tuple(c for _, c in scored)

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _score(prefix: str, candidate: str) -> float:
        """Score a candidate against a prefix (0.0–1.0)."""
        lower_prefix = prefix.lower()
        lower_cand = candidate.lower()

        if lower_cand == lower_prefix:
            return 1.0
        if lower_cand.startswith(lower_prefix):
            return 0.9
        if lower_prefix in lower_cand:
            return 0.6
        # Try fuzzy
        fuzzy = AutoComplete._fuzzy_score(lower_prefix, lower_cand)
        return fuzzy * 0.5 if fuzzy > 0.0 else 0.0

    @staticmethod
    def _fuzzy_score(query: str, candidate: str) -> float:
        """Subsequence-based fuzzy score (0.0–1.0)."""
        if not query:
            return 0.0
        qi = 0
        for ch in candidate:
            if qi < len(query) and ch == query[qi]:
                qi += 1
        if qi < len(query):
            return 0.0
        return qi / len(candidate) if candidate else 0.0
