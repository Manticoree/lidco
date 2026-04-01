"""Input preprocessor — abbreviations, macros and history search."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Macro:
    """A recorded keyboard macro."""

    name: str
    keys: tuple[str, ...]
    recorded_at: float


class InputPreprocessor:
    """Stateless helpers for input expansion, macros and history."""

    def __init__(self) -> None:
        self._macros: dict[str, Macro] = {}

    # -- abbreviation expansion -------------------------------------------

    def expand_abbreviation(self, text: str, abbreviations: dict[str, str]) -> str:
        """Expand known abbreviations in *text*.

        Each word that matches a key in *abbreviations* is replaced
        with its value.  Order is deterministic (left-to-right).
        """
        words = text.split()
        expanded = [abbreviations.get(w, w) for w in words]
        return " ".join(expanded)

    # -- macro recording --------------------------------------------------

    def record_macro(self, name: str, keys: list[str]) -> Macro:
        """Record a macro with *name* and return the frozen :class:`Macro`."""
        macro = Macro(name=name, keys=tuple(keys), recorded_at=time.time())
        self._macros = {**self._macros, name: macro}
        return macro

    def replay_macro(self, macro: Macro) -> list[str]:
        """Replay a macro, returning its key sequence as a list."""
        return list(macro.keys)

    # -- history search ---------------------------------------------------

    def search_history(self, query: str, history: tuple[str, ...]) -> tuple[str, ...]:
        """Return entries from *history* that contain *query* (case-insensitive)."""
        q = query.lower()
        return tuple(h for h in history if q in h.lower())
